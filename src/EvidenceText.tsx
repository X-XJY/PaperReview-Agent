import Markdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import './evidence.css';

const schema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [...(defaultSchema.attributes?.code || []), ['className', 'language-math', 'math-inline', 'math-display']],
  },
};

/** Parse MinerU table markup, sanitize it, then render trusted math output. */
export default function EvidenceText({ text }: { text: string }) {
  return <div className="evidence-text"><Markdown
    remarkPlugins={[remarkMath]}
    rehypePlugins={[rehypeRaw, [rehypeSanitize, schema], [rehypeKatex, { trust: false, maxExpand: 100, maxSize: 10 }]]}
    components={{ a: ({ children }) => <span>{children}</span>, img: () => null }}
  >{text}</Markdown></div>;
}
