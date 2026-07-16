import { useEffect, useRef, useState } from "react";
import type { AnimationItem } from "lottie-web";
import { loadLottie } from "../../lib/lottie";
import type { LottieAnimation } from "../../types";

interface Props {
  data: LottieAnimation | null;
  bg: string;
}

/**
 * Live Lottie preview with play/pause, scrub, speed, and loop controls.
 * Mirrors the control patterns from the engine's HTML player exporter.
 */
export default function LottiePreview({ data, bg }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const animRef = useRef<AnimationItem | null>(null);
  const [playing, setPlaying] = useState(true);
  const [looping, setLooping] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [frame, setFrame] = useState(0);
  const speeds = [0.25, 0.5, 1, 1.5, 2];

  // (Re)load animation whenever data changes.
  useEffect(() => {
    if (!hostRef.current || !data) return;
    animRef.current?.destroy();
    const anim = loadLottie(hostRef.current, data, { loop: looping, autoplay: playing });
    anim.setSpeed(speed);
    animRef.current = anim;

    const onEnter = () => setFrame(anim.currentFrame);
    anim.addEventListener("enterFrame", onEnter);
    return () => {
      anim.removeEventListener("enterFrame", onEnter);
      anim.destroy();
      animRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  const total = animRef.current?.totalFrames ?? 1;

  const togglePlay = () => {
    const a = animRef.current;
    if (!a) return;
    if (playing) {
      a.pause();
      setPlaying(false);
    } else {
      a.play();
      setPlaying(true);
    }
  };

  const onScrub = (val: number) => {
    const a = animRef.current;
    if (!a) return;
    a.goToAndStop((val / 100) * a.totalFrames, true);
    setFrame(a.currentFrame);
    setPlaying(false);
  };

  const cycleSpeed = () => {
    const idx = speeds.indexOf(speed);
    const next = speeds[(idx + 1) % speeds.length];
    setSpeed(next);
    animRef.current?.setSpeed(next);
  };

  const toggleLoop = () => {
    const next = !looping;
    setLooping(next);
    if (animRef.current) animRef.current.loop = next;
  };

  if (!data) {
    return (
      <div className="preview-host" style={{ background: bg }}>
        <p style={{ color: "var(--text-dim)" }}>
          No animation to preview. Add a <code>choreography</code> step to the scene.
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: bg }}>
      <div className="preview-host" style={{ flex: 1 }}>
        <div
          ref={hostRef}
          style={{ width: "100%", height: "100%", maxWidth: "100%", maxHeight: "100%" }}
        />
      </div>
      <div className="player-controls" style={{ background: "rgba(0,0,0,0.35)" }}>
        <button className="btn" onClick={togglePlay} title="Play/Pause">
          {playing ? "❚❚" : "▶"}
        </button>
        <input
          className="scrub"
          type="range"
          min={0}
          max={100}
          value={total ? (frame / total) * 100 : 0}
          onChange={(e) => onScrub(Number(e.target.value))}
        />
        <button className="btn" onClick={cycleSpeed} title="Speed">
          {speed}x
        </button>
        <button
          className="btn"
          onClick={toggleLoop}
          title="Loop"
          style={{ opacity: looping ? 1 : 0.4 }}
        >
          ↻
        </button>
      </div>
    </div>
  );
}
