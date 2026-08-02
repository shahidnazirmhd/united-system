import { Loader2, Search } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useDebouncedValue } from "@/hooks";
import { useLinkableEmployeesQuery } from "@/modules/users/hooks/useUserQueries";
import { useLinkUserToEmployeeMutation } from "@/modules/users/hooks/useUserMutations";
import type { ManagedUser } from "@/modules/users/types/user.types";
import { cn } from "@/lib/utils";

interface LinkUserToEmployeeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user: ManagedUser | undefined;
}

/**
 * "Link User to Employee" (Phase 12): search-as-you-type picker over
 * `GET /api/v1/employees/` (via `searchEmployeesForLinking`), then
 * `POST /api/v1/employees/{id}/link-user/`. A plain search box + result list
 * rather than a Radix Combobox — see `useEmployeeQueries.ts`'s
 * `useAllEmployeesQuery` docstring for the same "no new heavy dependency for
 * this phase's scope" reasoning.
 */
export function LinkUserToEmployeeDialog({ open, onOpenChange, user }: LinkUserToEmployeeDialogProps) {
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | null>(null);
  const { data: employees, isLoading } = useLinkableEmployeesQuery(debouncedSearch);
  const mutation = useLinkUserToEmployeeMutation();

  const handleClose = (nextOpen: boolean) => {
    if (!nextOpen) {
      setSearch("");
      setSelectedEmployeeId(null);
    }
    onOpenChange(nextOpen);
  };

  const handleLink = () => {
    if (!user || !selectedEmployeeId) return;
    mutation.mutate(
      { employeeId: selectedEmployeeId, userId: user.id },
      {
        onSuccess: () => {
          toast.success("Employee linked to this user.");
          handleClose(false);
        },
        onError: (error) => toast.error(error.message),
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Link to employee</DialogTitle>
          <DialogDescription>
            Choose the employee record {user?.email ? <strong>{user.email}</strong> : "this user"}{" "}
            should be linked to.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by name, code, or email…"
              className="pl-8"
              aria-label="Search employees"
            />
          </div>

          <div className="max-h-64 overflow-y-auto rounded-md border border-border">
            {isLoading ? (
              <div className="flex items-center justify-center gap-2 p-4 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                Searching…
              </div>
            ) : employees && employees.length > 0 ? (
              employees.map((employee) => (
                <button
                  key={employee.id}
                  type="button"
                  onClick={() => setSelectedEmployeeId(employee.id)}
                  className={cn(
                    "flex w-full flex-col items-start gap-0.5 border-b border-border px-3 py-2 text-left text-sm last:border-b-0 hover:bg-accent",
                    selectedEmployeeId === employee.id && "bg-accent",
                  )}
                >
                  <span className="font-medium text-foreground">{employee.fullName}</span>
                  <span className="text-xs text-muted-foreground">
                    {employee.employeeCode}
                    {employee.userId ? " · already linked to a different user" : ""}
                  </span>
                </button>
              ))
            ) : (
              <div className="p-4 text-center text-sm text-muted-foreground">No employees found.</div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button onClick={handleLink} disabled={!selectedEmployeeId || mutation.isPending}>
            {mutation.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
            Link employee
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
