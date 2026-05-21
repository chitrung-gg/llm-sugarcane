"use client"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Loader2 } from "lucide-react"

interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  onConfirm: () => void
  confirmLabel?: string
  isPending?: boolean
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  onConfirm,
  confirmLabel = "Delete",
  isPending = false,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-2xl sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle className="text-stone-900">{title}</DialogTitle>
          <DialogDescription className="text-stone-500 font-medium">
            {description}
          </DialogDescription>
        </DialogHeader>
        <div className="flex gap-3 justify-end pt-2">
          <Button
            variant="outline"
            className="rounded-xl font-bold"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            disabled={isPending}
            className="rounded-xl font-bold bg-red-600 hover:bg-red-700 text-white"
          >
            {isPending ? <Loader2 className="size-4 animate-spin" /> : confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
