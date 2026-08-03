import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

export default function MessageMarkdown({ content }: { content: string }) {
  return (
    <div className="jules-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  )
}
