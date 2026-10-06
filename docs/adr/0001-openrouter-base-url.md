# ADR-0001: Dùng OpenRouter làm provider LLM thống nhất

**Status**: accepted

Project được gọi là "tokenrouter" theo yêu cầu ban đầu, nhưng base URL thật là `https://openrouter.ai/api/v1` (OpenRouter). OpenRouter cung cấp cả chat completions và embeddings endpoint theo chuẩn OpenAI-compatible, hỗ trợ `tools` + `tool_choice` pass-through, và có model `:free` để demo. Mọi cuộc gọi LLM (chat + embedding) đều đi qua OpenRouter bằng `Authorization: Bearer <OPENROUTER_API_KEY>`. Đổi provider sau này chỉ cần đổi `BASE_URL` và `API_KEY` trong `.env` — không sửa code.