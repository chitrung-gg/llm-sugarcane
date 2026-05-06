import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { X, Plus, Trash2, RotateCcw, Send } from "lucide-react";

interface Step {
  step_id?: string | number;
  description: string;
  expected_tool?: string;
}

export function PlanModificationForm({ 
  initialPlan, 
  onSubmitEdits, 
  onSubmitFeedback, 
  onCancel 
}: {
  initialPlan: Step[];
  onSubmitEdits: (plan: Step[]) => void;
  onSubmitFeedback: (feedback: string) => void;
  onCancel: () => void;
}) {
  const [steps, setSteps] = useState<Step[]>(JSON.parse(JSON.stringify(initialPlan)));
  const [feedback, setFeedback] = useState("");

  const handleStepChange = (index: number, val: string) => {
    const newSteps = [...steps];
    newSteps[index].description = val;
    setSteps(newSteps);
  };

  const addStep = () => {
    setSteps([...steps, { description: "", expected_tool: "" }]);
  };

  const removeStep = (index: number) => {
    setSteps(steps.filter((_, i) => i !== index));
  };

  return (
    <div className="bg-white border-2 border-emerald-200 rounded-t-xl shadow-2xl p-4 animate-in slide-in-from-bottom duration-300">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-bold text-emerald-800 text-sm flex items-center gap-2">
          Modify Research Plan
        </h3>
        <button onClick={onCancel} className="h-8 w-8 flex items-center justify-center text-stone-400 hover:text-stone-600 transition-colors">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2 mb-4 custom-scrollbar">
        {steps.map((step, idx) => (
          <div key={idx} className="flex gap-2 items-start">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-800 font-bold text-[10px] mt-1.5">
              {idx + 1}
            </span>
            <div className="flex-1 space-y-2">
              <Textarea 
                value={step.description}
                onChange={(e) => handleStepChange(idx, e.target.value)}
                className="text-xs min-h-[60px] bg-stone-50 border-stone-200 focus-visible:ring-emerald-500"
                placeholder="Step description..."
              />
            </div>
            <button onClick={() => removeStep(idx)} className="text-stone-300 hover:text-red-500 mt-1 p-1 transition-colors">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        <Button variant="outline" size="sm" onClick={addStep} className="w-full border-dashed border-emerald-200 text-emerald-700 hover:bg-emerald-50 h-8 text-xs font-bold uppercase tracking-tight">
          <Plus className="h-3 w-3 mr-1" /> Add Custom Step
        </Button>
      </div>

      <div className="border-t pt-4 space-y-3">
        <div className="space-y-1.5">
            <label className="text-[10px] font-bold text-stone-400 uppercase tracking-widest ml-1">Or give text feedback for re-planning</label>
            <Textarea 
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="Ex: Don't use dataset X, focus on mutation patterns..."
                className="text-xs bg-stone-50 border-stone-200 focus-visible:ring-emerald-500"
            />
        </div>
        
        <div className="flex gap-2">
          <Button 
            className="flex-1 bg-emerald-700 hover:bg-emerald-800 text-white shadow-md text-xs font-bold uppercase tracking-tight h-10"
            onClick={() => onSubmitEdits(steps)}
          >
            <Send className="h-3.5 w-3.5 mr-1.5" /> Submit Edited Plan
          </Button>
          <Button 
            variant="outline" 
            className="flex-1 border-emerald-200 text-emerald-700 hover:bg-emerald-50 text-xs font-bold uppercase tracking-tight h-10"
            disabled={!feedback.trim()}
            onClick={() => onSubmitFeedback(feedback)}
          >
            <RotateCcw className="h-3.5 w-3.5 mr-1.5" /> Ask Agent to Re-plan
          </Button>
        </div>
      </div>
    </div>
  );
}
