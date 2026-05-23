export interface KnowledgeChunkOptions {
  max_chars: number
  overlap_chars: number
}

export interface KnowledgeDocumentPayload {
  source_doc_id: string
  source_name: string
  source_type: string
  source_url: string
  content: string
  language: string
  user_level: string
  tags: string[]
  metadata: Record<string, unknown>
  options: KnowledgeChunkOptions
  import_to_db: boolean
  deactivate_existing: boolean
  include_chunks: boolean
}

export interface KnowledgeChunkPreview {
  source_doc_id: string
  chunk_index: number
  chunk_text: string
  chunk_hash: string
  token_count: number
  char_count: number
  metadata: Record<string, unknown>
}

export interface KnowledgeDocumentResponse {
  source_doc_id: string
  chunk_count: number
  imported: boolean
  import_result: {
    total: number
    upserted_ids: number[]
    deactivated: Record<string, number>
  } | null
  chunks: KnowledgeChunkPreview[]
}
