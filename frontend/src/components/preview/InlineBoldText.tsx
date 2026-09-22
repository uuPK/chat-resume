// 用于安全渲染简历文本中的 **加粗** 标记。

import { Fragment } from 'react'

import { parseInlineBold } from '@/lib/resumeInlineFormat'

interface InlineBoldTextProps {
  text: string
}

/** 仅解释加粗标记，其余内容继续由 React 作为纯文本转义。 */
export default function InlineBoldText({ text }: InlineBoldTextProps) {
  return (
    <>
      {parseInlineBold(text).map((segment, index) => (
        <Fragment key={`${index}-${segment.text}`}>
          {segment.bold ? <strong>{segment.text}</strong> : segment.text}
        </Fragment>
      ))}
    </>
  )
}
