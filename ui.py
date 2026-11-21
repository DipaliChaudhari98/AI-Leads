"use client";

import { useMemo, useTransition } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { type Path, useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { isBefore, startOfDay } from "date-fns";

import { createDailyLog } from "@/actions/daily-log/create-daily-log";
import { updateDailyLog } from "@/actions/daily-log/update-daily-log";
import { DailyLogReview } from "@/components/daily-logs/daily-log-review";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/date-picker";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { FormInput } from "@/components/ui/form-input";
import { Input } from "@/components/ui/input";
import { Editor } from "@/components/ui/editor";
import { calculateTotalHours, hourFieldKeys } from "@/lib/daily-log";
import {
  dailyUpdateSchema,
  type DailyUpdateFormValues,
} from "@/schemas/daily-update";
import { useDialog } from "@/hooks/use-dialog";
import type { ActionError } from "@/types/action";
import type { DailyLogFormProps } from "@/types/daily-log";

function getDefaultValues(): DailyUpdateFormValues {
  return {
    logDate: new Date(),
    todaysUpdate: "",
    tomorrowTask: "",
    billableHours: 0,
    nonBillableHours: 0,
    upworkHours: 0,
    learningHours: 0,
    unproductiveHours: 0,
    totalHours: 0,
  };
}

export function DailyLogForm({
  initialValues,
  logId,
  mode = "create",
  unavailableLogDates = [],
}: DailyLogFormProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const dialog = useDialog();
  const [isPending, startTransition] = useTransition();

  const resolvedDefaultValues = useMemo(() => {
    const defaultValues = getDefaultValues();
    const queryDateParam = searchParams.get("date");

    if (queryDateParam && mode === "create" && !initialValues) {
      const parsedDate = new Date(queryDateParam);
      // Ensure date is valid and not in future
      if (
        !isNaN(parsedDate.getTime()) &&
        !isBefore(startOfDay(new Date()), startOfDay(parsedDate))
      ) {
        defaultValues.logDate = parsedDate;
      }
    }

    return {
      ...defaultValues,
      ...initialValues,
    };
  }, [initialValues, searchParams, mode]);

  const form = useForm<DailyUpdateFormValues>({
    resolver: zodResolver(dailyUpdateSchema),
    defaultValues: resolvedDefaultValues,
  });

  const watchedHours = useWatch({
    control: form.control,
    name: hourFieldKeys,
  });

  const watchedValues = useWatch({
    control: form.control,
  });

  const totalHours = calculateTotalHours(
    Object.fromEntries(
      hourFieldKeys.map((key, index) => [key, watchedHours[index]]),
    ) as Record<(typeof hourFieldKeys)[number], number>,
  );

  const submitLabel = mode === "update" ? "Update Daily Log" : "Save Daily Log";
  const confirmLabel = mode === "update" ? "Confirm Update" : "Confirm Submit";
  const disabledLogDates = useMemo(() => {
    const initialLogDate = initialValues?.logDate;

    if (!initialLogDate) {
      return unavailableLogDates;
    }

    return unavailableLogDates.filter(
      (date) => date.toDateString() !== new Date(initialLogDate).toDateString(),
    );
  }, [initialValues?.logDate, unavailableLogDates]);

  const applyActionErrors = (values: ActionError[]) => {
    values.forEach((error) => {
      if (!error.field) {
        return;
      }

      form.setError(error.field as Path<DailyUpdateFormValues>, {
        type: "server",
        message: error.message,
      });
    });
  };

  const handleConfirmedSubmit = (values: DailyUpdateFormValues) => {
    const payload = {
      ...values,
      totalHours,
    };

    return new Promise<boolean>((resolve) => {
      startTransition(() => {
        const submitAction =
          mode === "update" && logId
            ? updateDailyLog(logId, payload)
            : createDailyLog(payload);

        submitAction.then((response) => {
          if (!response.success) {
            if (response.errors?.length) {
              applyActionErrors(response.errors);
            }

            toast.error(response.message ?? "Unable to save the daily log.");
            resolve(false);
            return;
          }

          toast.success(response.message ?? "Daily log saved successfully.");

          router.push("/daily-logs");
          router.refresh();
          resolve(true);
        });
      });
    });
  };

  const handleOpenReview = async () => {
    const isValid = await form.trigger();

    if (!isValid) {
      toast.error("Please correct the highlighted fields before continuing.");
      return;
    }

    const reviewTitle =
      mode === "update"
        ? "Review Daily Log Update"
        : "Review Daily Log Submission";

    dialog.confirm({
      type: mode === "update" ? "update" : "submit",
      title: reviewTitle,
      description:
        "Verify the entered details before the final submission is sent to the server.",
      cancelLabel: "Edit",
      confirmLabel: confirmLabel,
      content: (
        <DailyLogReview
          values={{
            ...watchedValues,
            logDate: watchedValues.logDate ?? new Date(),
            todaysUpdate: watchedValues.todaysUpdate ?? "",
            tomorrowTask: watchedValues.tomorrowTask ?? "",
            billableHours: watchedValues.billableHours ?? 0,
            nonBillableHours: watchedValues.nonBillableHours ?? 0,
            upworkHours: watchedValues.upworkHours ?? 0,
            learningHours: watchedValues.learningHours ?? 0,
            unproductiveHours: watchedValues.unproductiveHours ?? 0,
            totalHours,
          }}
        />
      ),
      onConfirm: () =>
        new Promise<boolean>((resolve) => {
          void form.handleSubmit((values) => {
            handleConfirmedSubmit(values).then(resolve);
          })();
        }),
    });
  };

  return (
    <>
      <Form {...form}>
        <form className="space-y-6">
          <FormField
            control={form.control}
            name="logDate"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Update For Date</FormLabel>
                <FormControl>
                  <DatePicker
                    value={new Date(field.value)}
                    onChange={field.onChange}
                    disableMode="future"
                    disabledDates={disabledLogDates}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="todaysUpdate"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Today&apos;s Update</FormLabel>
                <FormControl>
                  <Editor
                    placeholder="Write your todays update..."
                    initialHtml={field.value}
                    onHtmlChange={field.onChange}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* <FormField
            control={form.control}
            name="tomorrowTask"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Tomorrow&apos;s Task</FormLabel>
                <FormControl>
                  <Editor
                    placeholder="Plan for tomorrow..."
                    initialHtml={field.value}
                    onHtmlChange={field.onChange}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          /> */}

          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Hours Summary</h2>

            {hourFieldKeys.map((key) => (
              <FormInput
                key={key}
                control={form.control}
                type="number"
                name={key}
                label={key.replace(/([A-Z])/g, " $1")}
                labelClassName="capitalize"
                step="0.25"
              />
            ))}

            <div className="space-y-2 rounded-xl border border-dashed p-4">
              <FormLabel>Total Hours</FormLabel>
              <Input disabled name="totalHours" value={totalHours.toFixed(2)} />
              <FormInput
                control={form.control}
                type="hidden"
                name="totalHours"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <Button
              asChild
              type="button"
              variant="outline"
              disabled={isPending}
            >
              <Link href="/daily-logs">Cancel</Link>
            </Button>
            <Button
              processing={isPending}
              type="button"
              onClick={() => {
                void handleOpenReview();
              }}
            >
              {isPending ? "Saving..." : submitLabel}
            </Button>
          </div>
        </form>
      </Form>
    </>
  );
}
