import { useMemo } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { yaml } from "@codemirror/lang-yaml";
import { EditorView } from "@codemirror/view";
import { useStudioStore } from "../../store/useStudioStore";

/** CodeMirror 6 YAML editor. YAML is the source of truth → triggers a recompile. */
export default function YamlEditor() {
  const value = useStudioStore((s) => s.yaml);
  const setYaml = useStudioStore((s) => s.setYaml);

  const extensions = useMemo(() => [yaml(), EditorView.lineWrapping], []);

  return (
    <div style={{ height: "100%", overflow: "auto" }}>
      <CodeMirror
        value={value}
        height="100%"
        theme="dark"
        extensions={extensions}
        onChange={setYaml}
        basicSetup={{
          lineNumbers: true,
          foldGutter: true,
          highlightActiveLine: true,
        }}
        style={{ fontSize: 13, height: "100%" }}
      />
    </div>
  );
}
