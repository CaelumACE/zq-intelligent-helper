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

/** 展演模式（欢迎页/登录页）自动编排的动作序列：idle 呼吸眨眼 → 轨道环绕 → comet 彗星 → burst 爆发 → wink */
const ATTRACT_STEPS: { state: BotState; duration: number }[] = [
  { state: 'idle', duration: 5.2 },
  { state: 'orbit', duration: 4.6 },
  { state: 'idle', duration: 2.2 },
  { state: 'comet', duration: 3.4 },
  { state: 'idle', duration: 2.2 },
  { state: 'burst', duration: 2.4 },
  { state: 'wink', duration: 1.6 },
]

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
  /**
   * 展演模式：组件自动编排 idle → orbit 轨道环绕 → comet 彗星 → burst 爆发 循环播放。
   * 用于欢迎页/登录页等品牌展示位；外部 state 仍优先（如登录中切 thinking）。
   */
  attract?: boolean
  /**
   * 庆祝信号：值变化时播放一次 burst 爆发动画后回到 state（用于回答完成等瞬间反馈）。
   */
  celebrateSignal?: number
  className?: string
  style?: CSSProperties
  title?: string
}

/**
 * 政企智能助手官方吉祥物——bloub 智能小球（MIT 授权，源自 jeremy-prt/bloub）。
 * 一个会变形的 SVG 小球：14 种状态（idle/thinking/orbit/burst…），
 * 思考时粒子脉冲，轨道环绕、彗星、爆发等展演状态让品牌位更生动。
 */
export default function BotAvatar({
  size = 36,
  state = 'idle',
  ink = '#0c4a6e',
  paper = '#ffffff',
  animated = true,
  frozenAt,
  attract = false,
  celebrateSignal,
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
      attract ? ATTRACT_STEPS[0].state : state,
      null,
      EXPRESSION_BY_ID.get('neutre') ?? null
    )
  }
  const engine = engineRef.current

  // inner：实际驱动引擎的状态（attract 编排 / celebrate 爆发时内部接管）
  const [inner, setInner] = useState<BotState>(attract ? ATTRACT_STEPS[0].state : state)
  const [frame, setFrame] = useState<BotFrame>(() => engine.sample(frozenAt ?? 0))
  const visibleRef = useRef(true)
  const wrapRef = useRef<HTMLSpanElement | null>(null)
  const busyRef = useRef(false) // celebrate/attract 正在播放时，外部 state 不打断
  const timersRef = useRef<number[]>([])
  const stateRef = useRef(state)
  stateRef.current = state

  const clearTimers = () => {
    timersRef.current.forEach((t) => window.clearTimeout(t))
    timersRef.current = []
  }

  // 外部受控状态变化；attract 编排期间，外部显式切到非 idle（如登录中 thinking）仍优先
  useEffect(() => {
    if (busyRef.current) return
    if (attract) {
      if (state !== 'idle') setInner(state)
      return
    }
    setInner(state)
  }, [state, attract])

  // 引擎跟随 inner 状态切换
  useEffect(() => {
    if (frozenAt !== undefined) return
    engine.setState(inner, performance.now() / 1000)
  }, [inner, engine, frozenAt])

  // 冻结帧
  useEffect(() => {
    if (frozenAt !== undefined) setFrame(engine.sample(frozenAt))
  }, [frozenAt, engine])

  // 庆祝信号：burst 爆发一次后回到外部 state
  const lastCelebrateRef = useRef<number | undefined>(celebrateSignal)
  useEffect(() => {
    if (celebrateSignal === undefined || celebrateSignal === lastCelebrateRef.current) return
    lastCelebrateRef.current = celebrateSignal
    if (frozenAt !== undefined || !animated) return
    clearTimers()
    busyRef.current = true
    setInner('burst')
    timersRef.current.push(window.setTimeout(() => {
      busyRef.current = false
      setInner(state)
    }, 2400))
    return clearTimers
  }, [celebrateSignal]) // eslint-disable-line react-hooks/exhaustive-deps

  // 展演模式：自动编排 orbit/comet/burst 等状态循环
  useEffect(() => {
    if (!attract || frozenAt !== undefined || !animated) return
    let cancelled = false
    let idx = 0
    let timer = 0
    const run = () => {
      if (cancelled) return
      const step = ATTRACT_STEPS[idx % ATTRACT_STEPS.length]
      if (!busyRef.current && stateRef.current === 'idle') setInner(step.state)
      idx += 1
      timer = window.setTimeout(run, step.duration * 1000)
    }
    timer = window.setTimeout(run, 600)
    return () => { cancelled = true; window.clearTimeout(timer) }
  }, [attract, frozenAt, animated])

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
    <span ref={wrapRef} className={className} style={{ display: 'inline-flex', lineHeight: 0, flexShrink: 0, position: 'relative', ...style }} title={title}>
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
