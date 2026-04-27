"use client";

import Link from "next/link";
import { ImagePlus } from "lucide-react";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const studioNavItems = [
  { href: "/", label: "单图创作", description: "保留现有公开生图首页", icon: ImagePlus },
];

export function StudioNav() {
  const pathname = usePathname();

  if (pathname === "/login") {
    return null;
  }

  return (
    <header className="pt-1">
      <div className="overflow-hidden rounded-[28px] border border-stone-200/80 bg-white/75 shadow-[0_20px_60px_rgba(120,113,108,0.08)] backdrop-blur">
        <div className="flex flex-col gap-4 px-4 py-4 sm:px-5">
          <div className="flex items-center justify-between gap-3">
            <div className="space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-stone-400">Public Studio</p>
              <div className="flex items-baseline gap-2">
                <h1 className="text-lg font-semibold tracking-tight text-stone-950">chatgpt2api-l</h1>
                <span className="text-sm text-stone-500">公开创作工作台</span>
              </div>
            </div>
            <div className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
              studio
            </div>
          </div>
          <nav className="grid gap-3">
            {studioNavItems.map((item) => {
              const active = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "group rounded-[22px] border px-4 py-4 transition",
                    active
                      ? "border-stone-900 bg-stone-950 text-stone-50 shadow-[0_18px_45px_rgba(28,25,23,0.2)]"
                      : "border-stone-200/80 bg-stone-50/80 text-stone-700 hover:border-stone-300 hover:bg-white",
                  )}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1.5">
                      <div className="text-sm font-semibold tracking-tight">{item.label}</div>
                      <p className={cn("text-sm leading-6", active ? "text-stone-300" : "text-stone-500")}>
                        {item.description}
                      </p>
                    </div>
                    <div
                      className={cn(
                        "rounded-2xl border p-2.5 transition",
                        active
                          ? "border-white/15 bg-white/10 text-stone-50"
                          : "border-stone-200 bg-white text-stone-700 group-hover:border-stone-300",
                      )}
                    >
                      <Icon className="size-4" />
                    </div>
                  </div>
                </Link>
              );
            })}
          </nav>
        </div>
      </div>
    </header>
  );
}
