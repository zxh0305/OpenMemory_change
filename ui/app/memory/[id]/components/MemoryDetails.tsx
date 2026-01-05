"use client";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { MemoryActions } from "./MemoryActions";
import { ArrowLeft, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { AccessLog } from "./AccessLog";
import Image from "next/image";
import Categories from "@/components/shared/categories";
import { useEffect, useState } from "react";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { constants } from "@/components/shared/source-app";
import { RelatedMemories } from "./RelatedMemories";

interface MemoryDetailsProps {
  memory_id: string;
}

export function MemoryDetails({ memory_id }: MemoryDetailsProps) {
  const router = useRouter();
  const { fetchMemoryById, hasUpdates } = useMemoriesApi();
  const memory = useSelector(
    (state: RootState) => state.memories.selectedMemory
  );
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (memory?.id) {
      await navigator.clipboard.writeText(memory.id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  useEffect(() => {
    fetchMemoryById(memory_id);
  }, []);

  return (
    <div className="container mx-auto py-6 px-4">
      <Button
        variant="ghost"
        className="mb-4 text-zinc-400 hover:text-white"
        onClick={() => router.back()}
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        Back to Memories
      </Button>
      <div className="flex gap-4 w-full">
        <div className="rounded-lg w-2/3 border h-fit pb-2 border-zinc-800 bg-zinc-900 overflow-hidden">
          <div className="">
            <div className="flex px-6 py-3 justify-between items-center mb-6 bg-zinc-800 border-b border-zinc-800">
              <div className="flex items-center gap-2">
                <h1 className="font-semibold text-white">
                  Memory{" "}
                  <span className="ml-1 text-zinc-400 text-sm font-normal">
                    #{memory?.id?.slice(0, 6)}
                  </span>
                </h1>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-4 w-4 text-zinc-400 hover:text-white -ml-[5px] mt-1"
                  onClick={handleCopy}
                >
                  {copied ? (
                    <Check className="h-3 w-3" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                </Button>
              </div>
              <MemoryActions
                memoryId={memory?.id || ""}
                memoryContent={memory?.text || ""}
                memoryState={memory?.state || ""}
              />
            </div>

            <div className="px-6 py-2">
              <div className="border-l-2 border-primary pl-4 mb-6">
                <p
                  className={`${
                    memory?.state === "archived" || memory?.state === "paused"
                      ? "text-zinc-400"
                      : "text-white"
                  }`}
                >
                  {memory?.text}
                </p>
              </div>

              <div className="mt-6 pt-4 border-t border-zinc-800">
                {/* 衰退信息卡片 */}
                <div className="mb-6 p-4 bg-zinc-800/50 rounded-lg border border-zinc-700">
                  <h3 className="text-sm font-semibold text-zinc-300 mb-3">衰退信息</h3>
                  <div className="grid grid-cols-2 gap-4">
                    {/* 衰退分数 */}
                    <div>
                      <div className="flex justify-between items-center mb-2">
                        <label className="text-xs text-zinc-400">衰退分数</label>
                        <span className={`text-lg font-bold ${
                          (memory?.decay_score ?? 1.0) >= 0.7 ? 'text-green-500' :
                          (memory?.decay_score ?? 1.0) >= 0.3 ? 'text-orange-500' :
                          'text-red-500'
                        }`}>
                          {((memory?.decay_score ?? 1.0) * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="w-full bg-zinc-700 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full transition-all ${
                            (memory?.decay_score ?? 1.0) >= 0.7 ? 'bg-green-500' :
                            (memory?.decay_score ?? 1.0) >= 0.3 ? 'bg-orange-500' :
                            'bg-red-500'
                          }`}
                          style={{ width: `${(memory?.decay_score ?? 1.0) * 100}%` }}
                        />
                      </div>
                      <p className="text-xs text-zinc-500 mt-1">
                        {(memory?.decay_score ?? 1.0) >= 0.7 ? '🟢 记忆新鲜' :
                         (memory?.decay_score ?? 1.0) >= 0.3 ? '🟡 记忆中等' :
                         '🔴 记忆衰退'}
                      </p>
                    </div>

                    {/* 重要性分数 */}
                    <div>
                      <div className="flex justify-between items-center mb-2">
                        <label className="text-xs text-zinc-400">重要性</label>
                        <span className="text-lg font-bold text-yellow-500">
                          {((memory?.importance_score ?? 0.5) * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="flex gap-1">
                        {[...Array(5)].map((_, i) => (
                          <svg
                            key={i}
                            className={`w-4 h-4 ${
                              i < Math.round((memory?.importance_score ?? 0.5) * 5)
                                ? 'text-yellow-400 fill-current'
                                : 'text-zinc-600'
                            }`}
                            viewBox="0 0 20 20"
                          >
                            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                          </svg>
                        ))}
                      </div>
                    </div>

                    {/* 访问次数 */}
                    <div className="bg-blue-900/20 p-3 rounded-lg border border-blue-800/30">
                      <div className="text-xs text-blue-400 mb-1">访问次数</div>
                      <div className="text-2xl font-bold text-blue-500">{memory?.access_count ?? 0}</div>
                    </div>
                    
                    {/* 最后访问 */}
                    <div className="bg-purple-900/20 p-3 rounded-lg border border-purple-800/30">
                      <div className="text-xs text-purple-400 mb-1">最后访问</div>
                      <div className="text-sm font-medium text-purple-500">
                        {memory?.last_accessed_at
                          ? new Date(memory.last_accessed_at * 1000).toLocaleDateString('zh-CN', {
                              year: 'numeric',
                              month: '2-digit',
                              day: '2-digit'
                            })
                          : '从未访问'}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex justify-between items-center">
                  <div className="">
                    <Categories
                      categories={memory?.categories || []}
                      isPaused={
                        memory?.state === "archived" ||
                        memory?.state === "paused"
                      }
                    />
                  </div>
                  <div className="flex items-center gap-2 min-w-[300px] justify-end">
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-1 bg-zinc-700 px-3 py-1 rounded-lg">
                        <span className="text-sm text-zinc-400">
                          Created by:
                        </span>
                        <div className="w-4 h-4 rounded-full bg-zinc-700 flex items-center justify-center overflow-hidden">
                          <Image
                            src={
                              constants[
                                memory?.app_name as keyof typeof constants
                              ]?.iconImage || ""
                            }
                            alt="OpenMemory"
                            width={24}
                            height={24}
                          />
                        </div>
                        <p className="text-sm text-zinc-100 font-semibold">
                          {
                            constants[
                              memory?.app_name as keyof typeof constants
                            ]?.name
                          }
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* <div className="flex justify-end gap-2 w-full mt-2">
                <p className="text-sm font-semibold text-primary my-auto">
                    {new Date(memory.created_at).toLocaleString()}
                  </p>
                </div> */}
              </div>
            </div>
          </div>
        </div>
        <div className="w-1/3 flex flex-col gap-4">
          <AccessLog memoryId={memory?.id || ""} />
          <RelatedMemories memoryId={memory?.id || ""} />
        </div>
      </div>
    </div>
  );
}
