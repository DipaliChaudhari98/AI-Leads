import os
import json
import asyncio
import logging
import time
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, LLM
from tools.db_tools import DatabaseManager
from models.apollo import ApolloLead
from models.sql_models import EmailOutreach

logger = logging.getLogger("EmailWorkflow")

# ─── Pipeline Logging Helpers ────────────────────────────────────────────────

def _agent_start(name: str) -> float:
    print(f"\n{'─'*60}")
    print(f"  🚀  {name} started")
    print(f"{'─'*60}")
    return time.time()

def _agent_done(name: str, start: float, count: int = None, extra: str = ""):
    elapsed = time.time() - start
    count_str = f" | Records: {count}" if count is not None else ""
    extra_str = f" | {extra}" if extra else ""
    print(f"  ✅  {name} completed in {elapsed:.2f}s{count_str}{extra_str}")

def _agent_error(name: str, error: Exception):
    print(f"  ❌  {name} FAILED: {error}")


class EmailContent(BaseModel):
    subject: str = Field(description="The email subject line.")
    body: str = Field(description="The email body content in plain text format.")

class EmailSequence(BaseModel):
    initial_message: EmailContent
    follow_up_1: EmailContent
    follow_up_2: EmailContent

class EmailWriterOutput(BaseModel):
    """Structured output from the EmailWriterAgent (single email — kept for backwards compat)."""
    subjectLine: str = Field(description="The email subject line.")
    emailBody: str = Field(description="The email body content in plain text format, 80-120 words.")
    personalizationUsed: List[str] = Field(default_factory=list, description="Fields actually used for personalization.")
    ignoredFields: List[str] = Field(default_factory=list, description="Fields that were unavailable or ignored.")

# ─── New structured output: 3-email sequence ────────────────────────────────
class EmailItem(BaseModel):
    """One email in the outreach sequence."""
    type: str = Field(description="Email type: initial | follow_up_1 | follow_up_2")
    subject: str = Field(description="Email subject line.")
    body: str = Field(description="Email body in plain text.")

class EmailSequenceOutput(BaseModel):
    """Full 3-email sequence returned by the new EmailWriterAgent."""
    emails: List[EmailItem] = Field(description="Ordered list of emails: initial, follow_up_1, follow_up_2.")
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ─── Sender Context (default SIGA values) ────────────────────────────────────
SIGA_SENDER_CONTEXT = {
    "companyName": "SIGA Systems AI",
    "services": [
        "AI Agents & Multi-Agent Systems",
        "Workflow Automation",
        "OCR & Intelligent Document Processing",
        "WhatsApp AI Chatbots",
        "Custom Software Development",
        "Web & E-commerce Development",
        "Cloud & DevOps",
        "API Development & Integrations",
        "Digital Marketing",
        "Technology Consulting"
    ],
    "valueProposition": "We help businesses grow by automating workflows, building AI-powered tools, and developing scalable digital solutions — so teams can focus on what drives real value.",
    "senderName": "Ashlesha",
    "meetingLink": "https://calendly.com/sigasystems"
}


class LeadDataValidationAgent:
    """
    Lead Data Validation Agent
    ──────────────────────────
    Sits before EmailWriterAgent in the email pipeline.

    Reads a lead record from the `leads` table, extracts AI scoring
    and profile fields, and determines whether there is sufficient
    personalization data to generate an LLM-powered email or whether
    the pipeline should use a fallback template.

    This agent does NOT:
      - Modify any database tables
      - Generate emails
      - Schedule or approve emails

    Returns a structured dict:
      {
        "lead": { ... extracted fields ... },
        "validation": {
          "is_personalizable": bool,
          "generation_method": "LLM" | "Fallback",
          "confidence": "High" | "Medium" | "Low",
          "personalization_sources": [list of available field names]
        }
      }
    """

    # The five primary fields used to decide personalization quality
    PRIMARY_FIELDS = [
        "ai_summary",
        "strengths",
        "weaknesses",
        "recommended_services",
        "next_action",
    ]

    @staticmethod
    def _has_value(val) -> bool:
        """Return True if a value is non-null and non-empty."""
        if val is None:
            return False
        if isinstance(val, str) and not val.strip():
            return False
        if isinstance(val, (list, dict)) and len(val) == 0:
            return False
        return True

    def _extract_lead_data(self, lead) -> Dict[str, Any]:
        """Extract the required fields from a Lead ORM object."""
        return {
            "name": lead.name,
            "company": lead.company,
            "designation": lead.title,
            "industry": lead.industry,
            "employee_count": lead.employee_count,
            "lead_score": lead.lead_score,
            "priority": lead.priority,
            "buying_probability": lead.buying_probability,
            "ai_summary": lead.ai_summary,
            "strengths": lead.strengths,
            "weaknesses": lead.weaknesses,
            "recommended_services": lead.recommended_services,
            "recommended_contact_role": lead.recommended_contact_role,
            "next_action": lead.next_action,
            "scoring_method": lead.scoring_method,
            "status": lead.status,
        }

    def _validate(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine generation_method, confidence, and personalization_sources
        from the extracted lead data.
        """
        # Identify which primary personalization fields have meaningful values
        available_sources: List[str] = []
        for field in self.PRIMARY_FIELDS:
            if self._has_value(lead_data.get(field)):
                available_sources.append(field)

        available_count = len(available_sources)
        total_primary = len(self.PRIMARY_FIELDS)
        lead_score = lead_data.get("lead_score") or 0

        # ── generation_method ────────────────────────────────────────────
        # "LLM" if most (>= 3 of 5) primary fields are present, else "Fallback"
        if available_count >= (total_primary // 2 + 1):  # >= 3 out of 5
            generation_method = "LLM"
        else:
            generation_method = "Fallback"

        # ── confidence ───────────────────────────────────────────────────
        has_summary = self._has_value(lead_data.get("ai_summary"))
        has_services = self._has_value(lead_data.get("recommended_services"))
        has_strengths = self._has_value(lead_data.get("strengths"))

        if has_summary and has_services and has_strengths and lead_score >= 70:
            confidence = "High"
        elif available_count >= 2 and 40 <= lead_score <= 69:
            confidence = "Medium"
        elif available_count >= 2 and lead_score >= 70:
            # Good score but partial data — still Medium
            confidence = "Medium"
        else:
            confidence = "Low"

        is_personalizable = generation_method == "LLM"

        return {
            "is_personalizable": is_personalizable,
            "generation_method": generation_method,
            "confidence": confidence,
            "personalization_sources": available_sources,
        }

    async def process(self, lead_id: int) -> Dict[str, Any]:
        """
        Main entrypoint.  Reads the lead from the DB by ID and returns
        the validation payload.
        """
        t = _agent_start("Lead Data Validation Agent")
        db_manager = DatabaseManager()
        try:
            from models.sql_models import Lead
            lead = db_manager.session.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                _agent_error("Lead Data Validation Agent", ValueError(f"Lead {lead_id} not found"))
                return {
                    "lead": None,
                    "validation": {
                        "is_personalizable": False,
                        "generation_method": "Fallback",
                        "confidence": "Low",
                        "personalization_sources": [],
                    },
                }

            lead_data = self._extract_lead_data(lead)
            validation = self._validate(lead_data)

            method_emoji = "LLM" if validation["generation_method"] == "LLM" else "Fallback"
            _agent_done(
                "Lead Data Validation Agent", t,
                extra=(
                    f"{lead.name} @ {lead.company} | "
                    f"Method: {method_emoji} | "
                    f"Confidence: {validation['confidence']} | "
                    f"Sources: {validation['personalization_sources']}"
                ),
            )
            return {
                "lead": lead_data,
                "validation": validation,
            }
        finally:
            db_manager.close()

    async def process_bulk(self, lead_ids: List[int]) -> List[Dict[str, Any]]:
        """Validate multiple leads in one pass (no DB writes)."""
        results = []
        for lid in lead_ids:
            results.append(await self.process(lid))
        return results


class LeadAgent:
    """Builds structured mergedData payload with source provenance for EmailWriterAgent."""
    async def process(self, lead: ApolloLead) -> Dict[str, Any]:
        logger.info(f"Lead Agent: Preparing structured mergedData for {lead.name} at {lead.company}")

        raw = lead.raw_data or {}
        company_obj = raw.get("company") or {}

        def _tagged(primary_keys, linkedin_fn, field_name):
            """Returns {value, source} using primary→linkedin fallback."""
            # Try primary keys from raw lead data first
            for k in primary_keys:
                v = raw.get(k)
                if v not in (None, "", [], {}):
                    return {"value": v, "source": "website"}
            # Try LinkedIn via callback
            try:
                li_val = linkedin_fn()
            except Exception:
                li_val = None
            if li_val not in (None, "", [], {}):
                return {"value": li_val, "source": "linkedin"}
            return {"value": None, "source": "none"}

        industries = company_obj.get("industries", [])
        positions = raw.get("currentPosition", []) or []
        tenure = positions[0].get("tenureText") if positions else None

        merged_data = {
            "companyName": _tagged(
                ["companyName", "company_name"],
                lambda: company_obj.get("name"),
                "companyName"
            ),
            "industry": _tagged(
                ["industry", "industry_name"],
                lambda: industries[0].get("name") if industries else None,
                "industry"
            ),
            "companySize": _tagged(
                ["employeeCount", "employee_count", "companySize"],
                lambda: company_obj.get("employeeCount") or raw.get("employeeCountRange"),
                "companySize"
            ),
            "companyLocation": _tagged(
                ["location", "apollo_location"],
                lambda: company_obj.get("location", {}).get("parsed", {}).get("text"),
                "companyLocation"
            ),
            "description": _tagged(
                ["description", "short_description", "aboutText"],
                lambda: company_obj.get("description"),
                "description"
            ),
            "specialities": _tagged(
                ["specialities", "technologies", "techStack"],
                lambda: company_obj.get("specialities"),
                "specialities"
            ),
            "hiring": _tagged(
                ["hiring"],
                lambda: raw.get("hiring"),
                "hiring"
            ),
            "openToWork": _tagged(
                ["openToWork"],
                lambda: raw.get("openToWork"),
                "openToWork"
            ),
            "decisionMaker": {
                "name": lead.name,
                "title": lead.title or (positions[0].get("position") if positions else None),
                "tenure": tenure,
                "source": "linkedin" if (lead.title or positions) else "none"
            },
            "pastRoles": raw.get("pastRoles") or [],
            "topSkills": raw.get("topSkills") or [],
            "alternateContacts": []
        }

        return {
            "name": lead.name,
            "company": lead.company,
            "mergedData": merged_data,
            "senderContext": SIGA_SENDER_CONTEXT,
            "lead": lead
        }

class EmailWriterAgent:
    """
    EmailWriterAgent — generates a 3-email outreach sequence.

    Input  : validation payload from LeadDataValidationAgent
             { "lead": {...}, "validation": {generation_method, confidence, personalization_sources} }

    Output : EmailSequenceOutput  (emails: [initial, follow_up_1, follow_up_2] + metadata)

    Rules
    ─────
    • Uses ONLY fields present in the lead record.
    • Never invents company achievements, news, tech stack, products, or awards.
    • LLM path  → when generation_method == "LLM" (>= 3 of 5 primary fields present)
    • Fallback  → when generation_method == "Fallback" (generic professional templates)
    • Does NOT update the database, approve, schedule, or send emails.
    """

    EMAIL_WRITER_PROMPT = """\
You are EmailWriterAgent.

Your ONLY responsibility is to generate a 3-email outreach sequence.

You are NOT allowed to:
- Invent company achievements, news, technologies, products, awards, or customer information.
- Infer facts not explicitly present in the input.
- Search for additional information.
- Update the database, approve emails, schedule emails, send emails, or call SendGrid.

==================================================
INPUT
==================================================
{input_json}

==================================================
RULES
==================================================
1. Use ONLY the information provided in the lead record.
2. Use these AI-intelligence fields whenever available (listed in personalization_sources):
   - ai_summary      → understand the lead's profile / company context
   - strengths       → highlight alignment with our services
   - weaknesses      → frame our services as the solution (without being blunt)
   - recommended_services → these are OUR services to pitch
   - next_action     → shape the CTA
3. Initial Email:
   - Introduce SIGA Systems AI naturally.
   - Mention why this lead was selected (use ai_summary / strengths if available).
   - Explain how our services relate to their needs.
   - Include a professional CTA with the meetingLink.
4. Follow-up 1:
   - Assume the first email was already sent.
   - Do NOT repeat the introduction.
   - Briefly reference the previous email.
   - Reinforce one additional benefit (use weaknesses or recommended_services if available).
   - Keep it shorter than the initial email.
5. Follow-up 2:
   - Final follow-up. Keep it concise.
   - Politely remind the recipient.
   - End with a soft CTA.
6. Do NOT use generic openings like "Hope you're doing well" or "Hope this finds you well".
7. Keep each email between 80 and 150 words.
8. Make emails conversational, professional, and human.

==================================================
SENDER CONTEXT
==================================================
{sender_json}

==================================================
OUTPUT — Return ONLY valid JSON, no markdown, no extra text.
==================================================
{{
  "emails": [
    {{"type": "initial",     "subject": "...", "body": "..."}},
    {{"type": "follow_up_1", "subject": "...", "body": "..."}},
    {{"type": "follow_up_2", "subject": "...", "body": "..."}}
  ],
  "metadata": {{
    "generation_method": "{generation_method}",
    "confidence": "{confidence}",
    "personalization_sources": {personalization_sources_json}
  }}
}}"""

    def __init__(self):
        from core.llm_config import get_llm
        self.llm = get_llm()

    # ── Fallback: deterministic 3-email sequence ─────────────────────────────
    def _fallback_sequence(
        self,
        lead_data: Dict[str, Any],
        validation: Dict[str, Any],
    ) -> EmailSequenceOutput:
        """Generic professional outreach sequence — no personalization attempted."""
        name = lead_data.get("name") or "there"
        company = lead_data.get("company") or "your company"
        sc = SIGA_SENDER_CONTEXT
        sender = sc["senderName"]
        sender_company = sc["companyName"]
        meeting = sc["meetingLink"]
        vp = sc["valueProposition"]

        subject_initial = f"Exploring a collaboration opportunity — {sender_company}"
        body_initial = (
            f"Hi {name},\n\n"
            f"I'm reaching out from {sender_company}. {vp}\n\n"
            f"We work with teams like yours to automate workflows, build AI-powered tools, "
            f"and develop scalable digital solutions — freeing your team to focus on what matters most.\n\n"
            f"Would a quick 15-minute conversation make sense? You can book a time here: {meeting}\n\n"
            f"Best regards,\n{sender}\n{sender_company}"
        )

        subject_fu1 = f"Re: {subject_initial}"
        body_fu1 = (
            f"Hi {name},\n\n"
            f"Just following up on my previous note about {sender_company}.\n\n"
            f"I know inboxes get busy — I wanted to make sure my message didn't get lost. "
            f"Beyond workflow automation, we also help teams with AI-driven insights and custom software "
            f"that reduce manual overhead significantly.\n\n"
            f"Happy to find 15 minutes that work for you: {meeting}\n\n"
            f"Best,\n{sender}\n{sender_company}"
        )

        subject_fu2 = f"Final note — {sender_company}"
        body_fu2 = (
            f"Hi {name},\n\n"
            f"One last follow-up — I don't want to overstay my welcome.\n\n"
            f"If scaling with AI solutions or automating workflows is on your radar this quarter, "
            f"I'd love to connect. If the timing isn't right, no worries at all.\n\n"
            f"Wishing {company} continued success!\n\n"
            f"Best,\n{sender}\n{sender_company}"
        )

        return EmailSequenceOutput(
            emails=[
                EmailItem(type="initial",     subject=subject_initial, body=body_initial),
                EmailItem(type="follow_up_1", subject=subject_fu1,     body=body_fu1),
                EmailItem(type="follow_up_2", subject=subject_fu2,     body=body_fu2),
            ],
            metadata={
                "generation_method": validation.get("generation_method", "Fallback"),
                "confidence":        validation.get("confidence", "Low"),
                "personalization_sources": validation.get("personalization_sources", []),
            },
        )

    # ── LLM path ─────────────────────────────────────────────────────────────
    async def process_validation(
        self,
        validation_payload: Dict[str, Any],
    ) -> EmailSequenceOutput:
        """
        Primary entrypoint — accepts the output of LeadDataValidationAgent.

        validation_payload = {
            "lead": { name, company, designation, ai_summary, strengths, ... },
            "validation": { generation_method, confidence, personalization_sources }
        }
        """
        import json as _json

        lead_data  = validation_payload.get("lead") or {}
        validation = validation_payload.get("validation") or {}
        name    = lead_data.get("name") or "?"
        company = lead_data.get("company") or "?"
        generation_method       = validation.get("generation_method", "Fallback")
        confidence              = validation.get("confidence", "Low")
        personalization_sources = validation.get("personalization_sources", [])

        t = _agent_start(f"EmailWriterAgent [{name} @ {company}] ({generation_method})")

        # ── Fallback path — no LLM call ──────────────────────────────────────
        if generation_method == "Fallback":
            result = self._fallback_sequence(lead_data, validation)
            _agent_done(f"EmailWriterAgent [{name}]", t, extra="Fallback")
            return result

        # ── Build prompt ─────────────────────────────────────────────────────
        # Limit ai_summary to 400 chars to keep prompt tight
        ai_summary = lead_data.get("ai_summary") or ""
        if ai_summary and len(ai_summary) > 400:
            ai_summary = ai_summary[:400].rstrip() + "..."

        lead_payload = {
            "name":                   name,
            "company":                company,
            "designation":            lead_data.get("designation"),
            "industry":               lead_data.get("industry"),
            "lead_score":             lead_data.get("lead_score"),
            "priority":               lead_data.get("priority"),
            "buying_probability":     lead_data.get("buying_probability"),
            "ai_summary":             ai_summary,
            "strengths":              lead_data.get("strengths"),
            "weaknesses":             lead_data.get("weaknesses"),
            "recommended_services":   lead_data.get("recommended_services"),
            "next_action":            lead_data.get("next_action"),
            "personalization_sources": personalization_sources,
        }

        prompt = self.EMAIL_WRITER_PROMPT.format(
            input_json=_json.dumps(lead_payload, indent=2, default=str),
            sender_json=_json.dumps(SIGA_SENDER_CONTEXT, indent=2),
            generation_method=generation_method,
            confidence=confidence,
            personalization_sources_json=_json.dumps(personalization_sources),
        )

        # ── CrewAI crew run (in thread to stay async) ────────────────────────
        class _SequenceOutput(BaseModel):
            emails: List[EmailItem]
            metadata: Dict[str, Any] = Field(default_factory=dict)

        def run_crew():
            agent = Agent(
                role="EmailWriterAgent",
                goal=(
                    "Generate a 3-email outreach sequence (initial, follow_up_1, follow_up_2) "
                    "using ONLY the supplied lead data. Return valid JSON."
                ),
                backstory=(
                    "You are a disciplined B2B email writing agent. You never invent facts. "
                    "You use ONLY the structured input to craft concise, human-sounding outreach emails. "
                    "You always return valid JSON with the keys: emails and metadata."
                ),
                llm=self.llm,
                verbose=False,
            )
            task = Task(
                description=prompt,
                expected_output=(
                    "Valid JSON with keys: emails (list of 3 objects with type/subject/body) "
                    "and metadata (generation_method, confidence, personalization_sources)."
                ),
                agent=agent,
                output_pydantic=_SequenceOutput,
            )
            crew = Crew(agents=[agent], tasks=[task], verbose=False)
            return crew.kickoff()

        try:
            loop = asyncio.get_running_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, run_crew),
                timeout=120.0,
            )
            if result.pydantic:
                seq_out = result.pydantic
                # Stamp metadata from our validation (source of truth)
                seq_out.metadata.update({
                    "generation_method": generation_method,
                    "confidence": confidence,
                    "personalization_sources": personalization_sources,
                })
                _agent_done(f"EmailWriterAgent [{name}]", t, extra="LLM")
                return EmailSequenceOutput(
                    emails=seq_out.emails,
                    metadata=seq_out.metadata,
                )
            else:
                raise ValueError("CrewAI did not return a valid Pydantic model.")
        except asyncio.TimeoutError:
            _agent_error(f"EmailWriterAgent [{name}]", Exception("Timed out after 120s"))
            logger.warning("EmailWriterAgent: LLM timed out — using fallback sequence.")
        except Exception as e:
            _agent_error(f"EmailWriterAgent [{name}]", e)
            logger.warning(f"EmailWriterAgent: LLM failed ({e}) — using fallback sequence.")

        # Deterministic fallback
        fb = self._fallback_sequence(lead_data, validation)
        _agent_done(f"EmailWriterAgent [{name}]", t, extra="fallback_after_llm_error")
        return fb

    # ── Legacy entrypoint (keeps EmailContentAgentWrapper working) ────────────
    async def process(self, context: Dict[str, Any]) -> EmailWriterOutput:
        """
        Legacy single-email entrypoint consumed by EmailContentAgentWrapper.
        Builds a minimal validation payload and delegates to process_validation,
        then returns only the initial email as EmailWriterOutput for compatibility.
        """
        import json as _json
        md = context.get("mergedData", {})
        dm = md.get("decisionMaker", {})
        lead_data = {
            "name":    dm.get("name") or context.get("name"),
            "company": md.get("companyName", {}).get("value") or context.get("company"),
            "designation": dm.get("title"),
            "industry":    md.get("industry", {}).get("value"),
            "ai_summary":  md.get("description", {}).get("value"),
            "recommended_services": md.get("specialities", {}).get("value"),
        }
        available = [f for f in ["ai_summary", "recommended_services"] if lead_data.get(f)]
        validation = {
            "generation_method": "LLM" if len(available) >= 1 else "Fallback",
            "confidence": "Medium",
            "personalization_sources": available,
        }
        seq = await self.process_validation({"lead": lead_data, "validation": validation})
        # Return initial email only as EmailWriterOutput
        initial = seq.emails[0] if seq.emails else EmailItem(type="initial", subject="", body="")
        return EmailWriterOutput(
            subjectLine=initial.subject,
            emailBody=initial.body,
            personalizationUsed=seq.metadata.get("personalization_sources", []),
            ignoredFields=[],
        )


# Backwards-compatible alias so existing orchestrator code keeps working
EmailContentAgent = EmailWriterAgent


class EmailContentAgentWrapper:
    """
    Thin wrapper that converts an EmailWriterOutput into the legacy
    EmailSequence format expected by FollowUpAgent and StorageAgent.
    """
    def __init__(self):
        self._writer = EmailWriterAgent()

    async def process(self, context: Dict[str, Any]) -> EmailSequence:
        t = _agent_start(f"Email Content Agent [{context['name']} @ {context['company']}]")
        logger.info(f"Email Content Agent (CrewAI): Generating sequence for {context['name']}...")
        
        prompt = f"""
        You are an elite B2B sales development representative specializing in personalized outbound outreach.

Generate a personalized 3-email outreach sequence for the following prospect:

Name: {context['name']}
Title: {context['title']}
Company: {context['company']}
Industry: {context['industry']}
Website: {context.get('website', '')}
Additional Context: {context.get('summary', '')}

Personalization Requirements

Before writing the emails:
- Research and understand the company’s industry, likely business goals, and growth focus.
- Tailor messaging based on the prospect’s role and company positioning.
- Mention relevant themes like: scaling teams, faster execution, operational efficiency, product growth, customer experience, delivery capacity, workflow optimization.

The email should feel:
- Thoughtfully researched
- Relevant to their business
- Conversational and human
- Strategic, not salesy

Outreach Goal
Position the outreach as:
- A potential collaboration
- Flexible team extension support
- Access to experienced developers when needed

Avoid sounding like generic outsourcing or aggressive sales outreach.

Writing Style
- Keep each email under 350 words
- Use short paragraphs
- Add natural hooks
- Use bold formatting for key phrases
- Keep the tone warm, confident, and professional
- End with a soft CTA

Follow-Up Guidance
Follow-Up 1
- Add fresh value or perspective
- Reference industry trends or execution challenges
- Stay conversational

Follow-Up 2
- Create gentle urgency without pressure
- Reinforce alignment and collaboration opportunity
- Encourage a quick exploratory conversation

Role-Based Messaging
- Founder / CEO: growth, scalability, execution speed
- VP / Director: productivity, operational efficiency
- Engineering Leaders: delivery bandwidth, technical support
- HR / Talent: hiring flexibility, access to skilled talent
- Sales / Marketing: engagement, pipeline efficiency
- Operations: workflow optimization, coordination
        """
        
        def run_crew():
            agent = Agent(
                role="B2B Sales Development Representative",
                goal="Generate a highly personalized 3-email outreach sequence.",
                backstory="You are an elite B2B sales development representative specializing in strategic, non-salesy outbound outreach that drives high response rates.",
                llm=self.llm,
                verbose=False
            )
            
            task = Task(
                description=prompt,
                expected_output="A structured 3-step email sequence.",
                agent=agent,
                output_pydantic=EmailSequence
            )
            
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=False
            )
            
            return crew.kickoff()
            
        try:
            # Run the synchronous CrewAI kickoff in a thread to preserve async workflow
            loop = asyncio.get_running_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, run_crew),
                timeout=90.0
            )
            
            if result.pydantic:
                _agent_done(f"Email Content Agent [{context['name']}]", t)
                return result.pydantic
            else:
                raise ValueError("CrewAI did not return a valid Pydantic model.")
                
        except asyncio.TimeoutError:
            _agent_error(f"Email Content Agent [{context['name']}]", Exception("Timed out after 90s"))
            logger.error(f"Email generation timed out for {context.get('name')} — using fallback sequence")
        except Exception as e:
            _agent_error(f"Email Content Agent [{context['name']}]", e)
            logger.error(f"Email generation failed via CrewAI: {e}")
        # ── Fallback sequence (used on both timeout and exception) ──────────
        return EmailSequence(
            initial_message=EmailContent(
                subject="Exploring a Strategic Resource Collaboration",
                body=f"""Hello {context.get('name', 'there')},

I hope you're doing well.

At SiGa Systems Pvt. Ltd., we partner with technology companies to bridge project resource gaps by engaging experienced software professionals on a flexible basis.

As our project portfolio continues to grow, we frequently require skilled developers with expertise in technologies such as Java, .NET, React, Angular, Python, Node.js, QA, DevOps, and other modern technology stacks.

We understand that companies like {context.get('company', 'your organization')} may occasionally have experienced professionals who are between client assignments. We'd like to explore a mutually beneficial partnership where we can engage such talent for our project needs while helping maximize your team's utilization.

If this aligns with your approach, I'd be happy to schedule a brief 10-minute conversation at your convenience.

Looking forward to hearing from you.

Best regards,

Ashlesha
Director
SiGa Systems Pvt. Ltd.

Email: ashlesha@sigasystems.com
WhatsApp: https://wa.me/918873511171"""
            ),
            follow_up_1=EmailContent(
                subject="Following up on our resource collaboration proposal",
                body=f"""Hello {context.get('name', 'there')},

I wanted to follow up on my previous email regarding a potential resource collaboration between SiGa Systems Pvt. Ltd. and {context.get('company', 'your organization')}.

We're looking to build partnerships with established IT companies by engaging experienced developers when they are between internal projects. This helps us meet project demands while creating additional utilization opportunities for your team.

If this is something your organization would be open to exploring, I'd be glad to schedule a brief 10-minute conversation.

Looking forward to your response.

Best regards,

Ashlesha
Director
SiGa Systems Pvt. Ltd.

Email: ashlesha@sigasystems.com
WhatsApp: https://wa.me/918873511171"""
            ),
            follow_up_2=EmailContent(
                subject="Final Follow-up: Resource Collaboration Opportunity",
                body=f"""Hello {context.get('name', 'there')},

I just wanted to send one final follow-up regarding my previous emails.

We regularly require experienced professionals across Java, .NET, React, Angular, Python, QA, DevOps, and other technology domains. We'd love to explore whether there's an opportunity to collaborate with {context.get('company', 'your organization')} whenever you have skilled professionals available between project assignments.

If this isn't the right time, I completely understand. Please feel free to reach out in the future if an opportunity arises.

Thank you for your time, and I wish you and your team continued success.

Warm regards,

Ashlesha
Director
SiGa Systems Pvt. Ltd.

Email: ashlesha@sigasystems.com
WhatsApp: https://wa.me/918873511171"""
            )
        )
        writer_output: EmailWriterOutput = await self._writer.process(context)
        name = context.get("name", "there")
        company = context.get("company", "your organization")
        sc = context.get("senderContext", SIGA_SENDER_CONTEXT)
        sender = sc.get("senderName", "Ashlesha")
        sender_company = sc.get("companyName", "SIGA Systems AI")
        meeting = sc.get("meetingLink", "https://calendly.com/sigasystems")

        follow_up_1_body = (
            f"Hi {name},\n\n"
            f"Just circling back on my earlier note about {sender_company}.\n\n"
            f"I know inboxes get busy — I just wanted to make sure this didn't get lost. "
            f"We've been helping teams automate repetitive workflows and build AI-powered tools "
            f"that save time and reduce manual overhead.\n\n"
            f"If you'd find 15 minutes useful, feel free to book here: {meeting}\n\n"
            f"Best,\n{sender}\n{sender_company}"
        )

        follow_up_2_body = (
            f"Hi {name},\n\n"
            f"Final follow-up — I don't want to overstay my welcome.\n\n"
            f"If automating workflows, building AI solutions, or scaling your digital capabilities "
            f"is on your radar in the next quarter, I'd love to connect. "
            f"If the timing isn't right, no worries at all — feel free to reach back out whenever.\n\n"
            f"Wishing you and the team at {company} continued success!\n\n"
            f"Best,\n{sender}\n{sender_company}"
        )

        return EmailSequence(
            initial_message=EmailContent(
                subject=writer_output.subjectLine,
                body=writer_output.emailBody
            ),
            follow_up_1=EmailContent(
                subject=f"Re: {writer_output.subjectLine}",
                body=follow_up_1_body
            ),
            follow_up_2=EmailContent(
                subject=f"Final note — {writer_output.subjectLine}",
                body=follow_up_2_body
            )
        )


class FollowUpAgent:
    """Organizes the emails into a sequence structure for storage."""
    async def process(self, sequence: EmailSequence, lead_id: int) -> List[Dict[str, Any]]:
        logger.info("Follow-Up Agent: Organizing sequence...")
        return [
            {"lead_id": lead_id, "type": "initial", "subject": sequence.initial_message.subject, "body": sequence.initial_message.body},
            {"lead_id": lead_id, "type": "follow_up_1", "subject": sequence.follow_up_1.subject, "body": sequence.follow_up_1.body},
            {"lead_id": lead_id, "type": "follow_up_2", "subject": sequence.follow_up_2.subject, "body": sequence.follow_up_2.body}
        ]

class StorageAgent:
    """Saves the organized emails into the existing Database (EmailOutreach)."""
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.lead_id = None

    async def process(self, emails: List[Dict[str, Any]], lead_id: int) -> bool:
        logger.info(f"Storage Agent: Storing {len(emails)} emails into the database...")
        loop = asyncio.get_running_loop()
        self.lead_id = lead_id
        
        def save_to_db():
            from datetime import datetime, timedelta
            from models.sql_models import Lead, EmailOutreach
            
            # Delete any existing email outreach records for this lead to avoid duplicates
            self.db_manager.session.query(EmailOutreach).filter(EmailOutreach.lead_id == self.lead_id).delete()
            
            lead = self.db_manager.session.query(Lead).filter(Lead.id == self.lead_id).first()
            if lead:
                lead.set_followup_dates()
                lead.status = "researched"
                
            for e in emails:
                days_offset = 0
                if e["type"] == "follow_up_1":
                    days_offset = 3
                elif e["type"] == "follow_up_2":
                    days_offset = 7
                
                    
                outreach = EmailOutreach(
                    lead_id=e["lead_id"],
                    subject=e["subject"],
                    body=e["body"],
                    status="draft",
                    type=e["type"],
                    scheduled_at=datetime.utcnow() + timedelta(days=days_offset)
                )
                self.db_manager.session.add(outreach)
            self.db_manager.session.commit()
            
        try:
            await asyncio.wait_for(
                loop.run_in_executor(None, save_to_db),
                timeout=30.0
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store emails: {e}")
            self.db_manager.session.rollback()
            return False
        finally:
            self.db_manager.close()

class EmailWorkflowOrchestrator:
    """Runs the entire email generation workflow for newly fetched leads."""
    def __init__(self):
        self.lead_agent = LeadAgent()
        self.email_agent = EmailContentAgentWrapper()  # uses EmailWriterAgent + builds EmailSequence
        self.followup_agent = FollowUpAgent()

    async def execute_for_leads(self, apollo_leads: List[ApolloLead], update_status_cb=None):
        if not apollo_leads:
            return
        
        pipeline_start = time.time()
        print("\n" + "═"*60)
        print("  📧  EMAIL WORKFLOW PIPELINE")
        print(f"  Generating sequences for {len(apollo_leads)} lead(s)")
        print("  Flow: Lead Agent → Email Content Agent → Follow-Up Agent → Storage Agent")
        print("═"*60)

        if update_status_cb: update_status_cb("Generating Email Sequences...")
        
        db_manager = DatabaseManager()
        # We need the actual Lead IDs from the database to store the emails
        emails = [lead.email for lead in apollo_leads if lead.email]
        db_leads = []
        if emails:
            # Import Lead model locally to avoid circular imports
            from models.sql_models import Lead
            db_leads = db_manager.session.query(Lead).filter(Lead.email.in_(emails)).all()
        db_manager.close()
        
        db_lead_map = {l.email.lower(): l.id for l in db_leads if l.email}

        tasks = []
        for lead in apollo_leads:
            if not lead.email or lead.email.lower() not in db_lead_map:
                continue
            
            lead_id = db_lead_map[lead.email.lower()]
            tasks.append(self._process_single_lead(lead, lead_id))
            
        await asyncio.gather(*tasks)
        total_time = time.time() - pipeline_start
        print("\n" + "═"*60)
        print("  🎉  EMAIL WORKFLOW COMPLETE")
        print(f"  Sequences generated for : {len(tasks)} lead(s)")
        print(f"  Total time              : {total_time:.2f}s")
        print("═"*60 + "\n")
        if update_status_cb: update_status_cb("Emails Generated and Stored.")

    async def _process_single_lead(self, lead: ApolloLead, lead_id: int):
        # Step 1: Validate lead data and determine personalization readiness
        validation_agent = LeadDataValidationAgent()
        validation_payload = await validation_agent.process(lead_id)

        # Check lead score threshold: score must be > 50% to generate email sequence, unless status is approved
        lead_data = validation_payload.get("lead") or {}
        lead_score = lead_data.get("lead_score") or 0
        lead_status = lead_data.get("status") or ""
        if lead_score <= 50 and lead_status != "approved":
            logger.info(f"Lead score is {lead_score}% (<= 50%) and not approved. Skipping email generation and sending lead {lead.name} to follow-ups.")
            return

        # Step 2: Generate 3-email sequence via EmailWriterAgent
        writer = EmailWriterAgent()
        seq_output: EmailSequenceOutput = await writer.process_validation(validation_payload)

        # Step 3: Convert EmailSequenceOutput → EmailSequence (for FollowUpAgent compat)
        def _item(email_type: str) -> EmailContent:
            for e in seq_output.emails:
                if e.type == email_type:
                    return EmailContent(subject=e.subject, body=e.body)
            return EmailContent(subject="", body="")

        sequence = EmailSequence(
            initial_message=_item("initial"),
            follow_up_1=_item("follow_up_1"),
            follow_up_2=_item("follow_up_2"),
        )

        organized_emails = await self.followup_agent.process(sequence, lead_id)

        storage_agent = StorageAgent()
        await storage_agent.process(organized_emails, lead_id)

async def run_email_pipeline(leads: List[ApolloLead], update_status_cb=None):
    orchestrator = EmailWorkflowOrchestrator()
    await orchestrator.execute_for_leads(leads, update_status_cb)
