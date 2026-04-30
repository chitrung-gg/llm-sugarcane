"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import * as z from "zod"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { FlaskConical, AlertCircle, Sprout } from "lucide-react"

const loginSchema = z.object({
  email: z.string().email({ message: "Enter a valid email." }),
  password: z.string().min(6, { message: "Password must be at least 6 characters." }),
})

type LoginFormValues = z.infer<typeof loginSchema>

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState(false)
  const router = useRouter()

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  })

  async function onSubmit() {
    setIsLoading(true)
    setTimeout(() => {
      setIsLoading(false)
      router.push("/dashboard")
    }, 600)
  }

  return (
    <div className="min-h-screen flex flex-col bg-stone-50 font-sans antialiased text-stone-900">
      <header className="w-full px-8 py-4 flex items-center justify-between border-b border-stone-200 bg-white/80 backdrop-blur-md sticky top-0 z-50">
        <div className="flex items-center gap-2.5">
          <div className="bg-emerald-700 p-1.5 rounded-lg shadow-sm">
            <Sprout className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-black tracking-tight text-stone-900">Sugarcane LLM</h1>
            <p className="text-[10px] uppercase tracking-widest font-bold text-emerald-700/70">Genomic Intelligence</p>
          </div>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <Card className="border-stone-200 shadow-xl shadow-stone-200/50 rounded-2xl bg-white overflow-hidden">
            <CardHeader className="space-y-1 pt-10 pb-6 text-center">
              <div className="mx-auto bg-stone-50 w-16 h-16 rounded-2xl flex items-center justify-center mb-4 border border-stone-100">
                <FlaskConical className="h-8 w-8 text-emerald-700" />
              </div>
              <CardTitle className="text-2xl font-bold text-stone-900">Welcome Back</CardTitle>
              <CardDescription className="text-stone-500 font-medium">
                Sign in to your sugarcane research workspace
              </CardDescription>
            </CardHeader>
            
            <form onSubmit={handleSubmit(onSubmit)}>
              <CardContent className="px-8 space-y-5">
                <div className="space-y-1.5">
                  <Label htmlFor="email" className="text-xs font-bold text-stone-500 uppercase tracking-wider ml-1">Email</Label>
                  <Input 
                    id="email" 
                    type="email" 
                    placeholder="name@example.com"
                    className="h-11 rounded-xl border-stone-200 bg-stone-50/50 focus-visible:ring-emerald-500 focus-visible:border-emerald-500 transition-all"
                    {...register("email")}
                  />
                  {errors.email && (
                    <p className="text-[10px] text-red-500 flex items-center gap-1 mt-1 font-bold uppercase ml-1">
                      <AlertCircle className="h-3 w-3" /> {errors.email.message}
                    </p>
                  )}
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between ml-1">
                    <Label htmlFor="password" title="password" className="text-xs font-bold text-stone-500 uppercase tracking-wider">Password</Label>
                  </div>
                  <Input 
                    id="password" 
                    type="password" 
                    placeholder="••••••••"
                    className="h-11 rounded-xl border-stone-200 bg-stone-50/50 focus-visible:ring-emerald-500 focus-visible:border-emerald-500 transition-all"
                    {...register("password")}
                  />
                  {errors.password && (
                    <p className="text-[10px] text-red-500 flex items-center gap-1 mt-1 font-bold uppercase ml-1">
                      <AlertCircle className="h-3 w-3" /> {errors.password.message}
                    </p>
                  )}
                </div>
              </CardContent>

              <CardFooter className="px-8 pt-6 pb-10 flex flex-col space-y-4">
                <Button 
                  className="w-full h-12 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-bold transition-all shadow-lg shadow-emerald-700/20 active:scale-[0.98]" 
                  type="submit" 
                  disabled={isLoading}
                >
                  {isLoading ? "Signing in..." : "Enter Workspace"}
                </Button>
                
                <p className="text-center text-[10px] text-stone-400 font-medium leading-relaxed">
                  Sugarcane Thesis Project • 2026
                </p>
              </CardFooter>
            </form>
          </Card>
        </div>
      </main>

      <footer className="w-full py-6 text-center">
        <p className="text-[10px] font-bold text-stone-300 uppercase tracking-[0.3em]">
          Genomic Intelligence System
        </p>
      </footer>
    </div>
  )
}
