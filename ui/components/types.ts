export type Category = "personal" | "work" | "health" | "finance" | "travel" | "education" | "preferences" | "relationships"
export type Client = "chrome" | "chatgpt" | "cursor" | "windsurf" | "terminal" | "api"

export interface Memory {
  id: string
  memory: string
  metadata: any
  client: Client
  categories: Category[]
  created_at: number
  app_name: string
  state: "active" | "paused" | "archived" | "deleted"
  
  // 衰退相关字段
  decay_score?: number        // 衰退分数 (0.0-1.0)
  importance_score?: number   // 重要性分数 (0.0-1.0)
  access_count?: number       // 访问次数
  last_accessed_at?: number   // 最后访问时间戳
}