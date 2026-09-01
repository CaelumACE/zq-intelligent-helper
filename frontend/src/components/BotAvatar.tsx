import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { BotEngine, type BotFrame } from '../bot/engine'
import { EXPRESSION_BY_ID } from '../bot/expressions'
import { DEMI_VIEWBOX, RAYON } from '../bot/repere'
import { NOTIF_BLUE } from '../bot/decor'
import { mixHex } from '../bot/skins'

/** bloub 引擎支持的状态名（见 src/bot/states.ts） */
export type BotState =
  | 'idle' | 'thinking' | 'wink' | 'wide' | 'alert' | 'notify'
  | 'exclaim' | 'sleep' | 'egg' | 'hexagon' | 'play'
  | 'orbit' | 'burst' | 'comet' | 'swirl'

interface BotAvatarProps {
  /** 渲染尺寸 px */
  size?: number
  /** 动画状态；loading 场景用 'thinking'，完成/空闲用 'idle' */
  state?: BotState
  /** 身体（主体）颜色，默认政务蓝 */
  ink?: string
  /** 底色（眼睛孔洞透出的颜色），默认白色；反色场景传容器底色 */
  paper?: string
  /** 是否开启动画（历史消息静态头像可传 false） */
  animated?: boolean
  /** 静态帧：冻结在状态开始后 N 秒（设置后不跑动画循环） */
  frozenAt?: number
  className?: string
  style?: CSSProperties
  title?: string
}

/**
 * 政企智能助手官方吉祥物——bloub 智能小球（MIT 授权，源自 jeremy-prt/bloub）。
 * 一个会变形的 SVG 小球：14 种状态（idle/thinking/orbit/burst…），
 * 思考时环形轨道旋转，回答完回到 idle 眨眼呼吸。
 */
export default function BotAvatar({
  size = 36,
  state = 'idle',
  ink = '#0c4a6e',
  paper = '#ffffff',
  animated = true,
  frozenAt,
  className,
  style,
  title,
}: BotAvatarProps) {
  const R = RAYON
  const VB = DEMI_VIEWBOX
  const uidRef = useRef(Math.random().toString(36).slice(2, 8))
  const maskId = `bot-mask-${uidRef.current}`

  const engineRef = useRef<BotEngine | null>(null)
  if (!engineRef.current) {
    engineRef.current = new BotEngine(
      R,
      state,
      null,
      EXPRESSION_BY_ID.get('neutre') ?? null
    )
  }
  const engine = engineRef.current

  const [frame, setFrame] = useState<BotFrame>(() => engine.sample(frozenAt ?? 0))
  const visibleRef = useRef(true)
  const wrapRef = useRef<HTMLSpanElement | null>(null)

  // 状态切换
  useEffect(() => {
    if (frozenAt !== undefined) return
    engine.setState(state, performance.now() / 1000)
  }, [state, engine, frozenAt])

  // 冻结帧
  useEffect(() => {
    if (frozenAt !== undefined) setFrame(engine.sample(frozenAt))
  }, [frozenAt, engine])

  // 视口外暂停（页面上头像多时省电）
  useEffect(() => {
    if (!animated || frozenAt !== undefined) return
    const el = wrapRef.current
    if (el && typeof IntersectionObserver !== 'undefined') {
      const io = new IntersectionObserver(
        (entries) => { visibleRef.current = entries[0]?.isIntersecting ?? true },
        { threshold: 0.05 }
      )
      io.observe(el)
      return () => io.disconnect()
    }
  }, [animated, frozenAt])

  // 动画循环
  useEffect(() => {
    if (!animated || frozenAt !== undefined) return
    let raf = 0
    let mounted = true
    const tick = () => {
      if (!mounted) return
      if (visibleRef.current) {
        setFrame(engine.sample(performance.now() / 1000))
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => { mounted = false; cancelAnimationFrame(raf) }
  }, [animated, frozenAt, engine])

  const dotAttrs = (dot: BotFrame['dots'][number]) => {
    const fill = dot.color ?? (dot.depth === undefined ? ink : mixHex(paper, ink, dot.depth))
    const common = { fill, opacity: dot.opacity }
    return dot.d
      ? { ...common, d: dot.d, transform: `translate(${dot.x} ${dot.y}) rotate(${dot.rot ?? 0}) scale(${R})` }
      : { ...common, cx: dot.x, cy: dot.y, r: dot.r }
  }

  return (
    <span ref={wrapRef} className={className} style={{ display: 'inline-flex', lineHeight: 0, flexShrink: 0, ...style }} title={title}>
      <svg width={size} height={size} viewBox={`${-VB} ${-VB} ${VB * 2} ${VB * 2}`} role="img" aria-label={title || '智能助手'}>
        <defs>
          <mask id={maskId} maskUnits="userSpaceOnUse" x={-VB} y={-VB} width={VB * 2} height={VB * 2}>
            <path d={frame.bodyPath} fill="#fff" />
            {frame.eyes.map((eye, i) => (
              <path key={i} d={eye.d} transform={eye.matrix} opacity={eye.alpha} fill="#000" />
            ))}
            {frame.notch && <circle cx={frame.notch.x} cy={frame.notch.y} r={frame.notch.r} fill="#000" />}
          </mask>
          {frame.arcs.map((arc) => (
            <linearGradient
              key={arc.id}
              id={`${uidRef.current}-${arc.id}`}
              gradientUnits="userSpaceOnUse"
              x1={arc.grad.x1} y1={arc.grad.y1} x2={arc.grad.x2} y2={arc.grad.y2}
            >
              {arc.grad.stops.map((c, i) => (
                <stop key={i} offset={i / (arc.grad.stops.length - 1)} stopColor={c} />
              ))}
            </linearGradient>
          ))}
        </defs>

        {/* 轨道后半（被身体遮挡） */}
        <g fill="none" strokeLinecap="round">
          {frame.arcs.map((arc) => (
            <path key={`b${arc.id}`} d={arc.back} stroke={`url(#${uidRef.current}-${arc.id})`} strokeWidth={arc.width} opacity={arc.opacity} />
          ))}
        </g>

        {/* 粒子在身后 */}
        {frame.dotsBehind && frame.dots.map((dot, i) => (
          dot.d
            ? <path key={`pb${i}`} {...dotAttrs(dot)} />
            : <circle key={`pb${i}`} {...dotAttrs(dot)} />
        ))}

        <g opacity={frame.bodyAlpha}>
          {/* 身体底色衬底（保证眼睛孔洞不透出轨道） */}
          <path d={frame.bodyPath} fill={paper} />
          <g mask={`url(#${maskId})`}>
            <rect x={-VB} y={-VB} width={VB * 2} height={VB * 2} fill={ink} />
          </g>
        </g>

        {/* 粒子在身前 */}
        {!frame.dotsBehind && frame.dots.map((dot, i) => (
          dot.d
            ? <path key={`pf${i}`} {...dotAttrs(dot)} />
            : <circle key={`pf${i}`} {...dotAttrs(dot)} />
        ))}

        {frame.notif && <circle cx={frame.notif.x} cy={frame.notif.y} r={frame.notif.r} fill={NOTIF_BLUE} />}

        {/* 轨道前半 */}
        <g fill="none" strokeLinecap="round">
          {frame.arcs.map((arc) => (
            <path key={`f${arc.id}`} d={arc.front} stroke={`url(#${uidRef.current}-${arc.id})`} strokeWidth={arc.width} opacity={arc.opacity} />
          ))}
        </g>
      </svg>
    </span>
  )
}
