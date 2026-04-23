"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { LoaderCircle } from "lucide-react";
import { toast } from "sonner";

import { ActivationCodeTable, GeneratorSection } from "@/app/billing/billing-page-codes";
import { BillingHero, PricingSection } from "@/app/billing/billing-page-sections";
import {
  createAdminActivationCodes,
  fetchAdminActivationCodes,
  fetchAdminModelPricing,
  updateAdminModelPricing,
  type AdminActivationCode,
  type AdminActivationCodeStatus,
  type AdminModelPricing,
} from "@/lib/api";

type PricingDrafts = Record<string, { price: string; enabled: boolean }>;

function buildPricingDrafts(items: AdminModelPricing[]): PricingDrafts {
  return Object.fromEntries(items.map((item) => [item.model, { price: item.price, enabled: item.enabled === "1" }]));
}

export default function BillingPageClient() {
  const didLoadRef = useRef(false);
  const [pricingItems, setPricingItems] = useState<AdminModelPricing[]>([]);
  const [pricingDrafts, setPricingDrafts] = useState<PricingDrafts>({});
  const [activationCodes, setActivationCodes] = useState<AdminActivationCode[]>([]);
  const [generatedCodes, setGeneratedCodes] = useState<AdminActivationCode[]>([]);
  const [statusFilter, setStatusFilter] = useState<"all" | AdminActivationCodeStatus>("all");
  const [batchNoteFilter, setBatchNoteFilter] = useState("");
  const [redeemedUsernameFilter, setRedeemedUsernameFilter] = useState("");
  const [createCount, setCreateCount] = useState("10");
  const [createAmount, setCreateAmount] = useState("9.90");
  const [createBatchNote, setCreateBatchNote] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isListLoading, setIsListLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [savingModel, setSavingModel] = useState<string | null>(null);

  const loadActivationCodes = async (silent = false) => {
    if (!silent) setIsListLoading(true);
    try {
      const params = {
        ...(statusFilter !== "all" ? { status: statusFilter } : {}),
        ...(batchNoteFilter.trim() ? { batch_note: batchNoteFilter.trim() } : {}),
        ...(redeemedUsernameFilter.trim() ? { redeemed_username: redeemedUsernameFilter.trim() } : {}),
      };
      const data = await fetchAdminActivationCodes(params);
      setActivationCodes(data.items);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载激活码失败");
    } finally {
      if (!silent) setIsListLoading(false);
    }
  };

  const loadPage = async () => {
    setIsLoading(true);
    try {
      const [pricingData, codeData] = await Promise.all([fetchAdminModelPricing(), fetchAdminActivationCodes()]);
      setPricingItems(pricingData.items);
      setPricingDrafts(buildPricingDrafts(pricingData.items));
      setActivationCodes(codeData.items);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载商业化配置失败");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (didLoadRef.current) return;
    didLoadRef.current = true;
    void loadPage();
  }, []);

  const summary = useMemo(() => {
    const enabledModels = pricingItems.filter((item) => item.enabled === "1").length;
    const unusedCodes = activationCodes.filter((item) => item.status === "unused").length;
    const redeemedCodes = activationCodes.length - unusedCodes;
    return { enabledModels, unusedCodes, redeemedCodes };
  }, [activationCodes, pricingItems]);

  const updateDraft = (model: string, patch: Partial<{ price: string; enabled: boolean }>) => {
    setPricingDrafts((prev) => ({ ...prev, [model]: { ...prev[model], ...patch } }));
  };

  const handleSavePricing = async (model: string) => {
    const draft = pricingDrafts[model];
    if (!draft) return;
    setSavingModel(model);
    try {
      const data = await updateAdminModelPricing({ model, price: draft.price.trim(), enabled: draft.enabled });
      setPricingItems(data.items);
      setPricingDrafts(buildPricingDrafts(data.items));
      toast.success("模型价格已更新");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存模型价格失败");
    } finally {
      setSavingModel(null);
    }
  };

  const handleCreateCodes = async () => {
    setIsCreating(true);
    try {
      const data = await createAdminActivationCodes({
        count: Number(createCount),
        amount: createAmount.trim(),
        batch_note: createBatchNote.trim(),
      });
      setGeneratedCodes(data.items);
      toast.success(`已生成 ${data.items.length} 个激活码`);
      await loadActivationCodes(true);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "生成激活码失败");
    } finally {
      setIsCreating(false);
    }
  };

  const copyGeneratedCodes = async () => {
    if (generatedCodes.length === 0) {
      toast.error("暂无可复制的激活码");
      return;
    }
    try {
      await navigator.clipboard.writeText(generatedCodes.map((item) => item.code).join("\n"));
      toast.success("激活码已复制");
    } catch {
      toast.error("复制失败");
    }
  };

  const resetFilters = async () => {
    setStatusFilter("all");
    setBatchNoteFilter("");
    setRedeemedUsernameFilter("");
    setIsListLoading(true);
    try {
      const data = await fetchAdminActivationCodes();
      setActivationCodes(data.items);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "重置筛选失败");
    } finally {
      setIsListLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <LoaderCircle className="size-8 animate-spin text-stone-500" />
      </div>
    );
  }

  return (
    <div className="space-y-5 pb-8">
      <BillingHero pricingCount={pricingItems.length} enabledModels={summary.enabledModels} unusedCodes={summary.unusedCodes} />

      <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <PricingSection
          items={pricingItems}
          drafts={pricingDrafts}
          savingModel={savingModel}
          onPriceChange={(model, value) => updateDraft(model, { price: value })}
          onEnabledChange={(model, checked) => updateDraft(model, { enabled: checked })}
          onSave={(model) => void handleSavePricing(model)}
        />
        <GeneratorSection
          count={createCount}
          amount={createAmount}
          batchNote={createBatchNote}
          generatedCodes={generatedCodes}
          isCreating={isCreating}
          onCountChange={setCreateCount}
          onAmountChange={setCreateAmount}
          onBatchNoteChange={setCreateBatchNote}
          onCreate={() => void handleCreateCodes()}
          onCopy={() => void copyGeneratedCodes()}
        />
      </div>

      <ActivationCodeTable
        items={activationCodes}
        statusFilter={statusFilter}
        batchNoteFilter={batchNoteFilter}
        redeemedUsernameFilter={redeemedUsernameFilter}
        isListLoading={isListLoading}
        redeemedCount={summary.redeemedCodes}
        onStatusChange={setStatusFilter}
        onBatchNoteChange={setBatchNoteFilter}
        onRedeemedUsernameChange={setRedeemedUsernameFilter}
        onApplyFilters={() => void loadActivationCodes()}
        onResetFilters={() => void resetFilters()}
      />
    </div>
  );
}
