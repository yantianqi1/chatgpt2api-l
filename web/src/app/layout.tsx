import type { Metadata } from "next";
import { Toaster } from "sonner";
import "./globals.css";
import { TopNav } from "@/components/top-nav";
import { getAppVariant } from "@/lib/app-variant";

const isStudio = getAppVariant() === "studio";

export const metadata: Metadata = isStudio
  ? {
      title: "匿名公共生图面板",
      description: "无需登录，直接生成和编辑图片",
    }
  : {
      title: "ChatGPT 号池管理",
      description: "ChatGPT account pool management dashboard",
    };

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body
        className="antialiased"
        style={{
          fontFamily:
            '"SF Pro Display","SF Pro Text","PingFang SC","Microsoft YaHei","Helvetica Neue",sans-serif',
        }}
      >
        <Toaster position="top-center" richColors />
        <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.92),_rgba(245,239,231,0.96)_42%,_rgba(240,235,227,0.99)_100%)] px-4 py-2 text-stone-900 sm:px-6 lg:px-8">
          <div className={`mx-auto flex flex-col gap-5 ${isStudio ? "max-w-[1380px]" : "max-w-[1440px]"}`}>
            {isStudio ? null : <TopNav />}
            {children}
          </div>
        </main>
      </body>
    </html>
  );
}
