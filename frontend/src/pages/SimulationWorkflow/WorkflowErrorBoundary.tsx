import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { clearWorkflowSession } from "./workflowSession";

type Props = {
  simulationId: string;
  children: ReactNode;
};

type State = {
  error: Error | null;
};

export class WorkflowErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Workflow rendering failed", error, info);
  }

  private reset = () => {
    clearWorkflowSession(this.props.simulationId);
    window.location.reload();
  };

  private back = () => {
    window.history.pushState(null, "", "/projects");
    window.dispatchEvent(new PopStateEvent("popstate"));
  };

  render() {
    if (!this.state.error) return this.props.children;
    return <main className="workflow-error" role="alert">
      <p className="eyebrow">WORKFLOW ERROR</p>
      <h1>Workflow tidak dapat ditampilkan.</h1>
      <p>Data proyek tetap tersimpan. Atur ulang sesi workflow untuk mencoba kembali dari tahap terakhir yang tersimpan.</p>
      <details><summary>Detail teknis</summary><code>{this.state.error.message}</code></details>
      <div className="actions"><button className="button primary" onClick={this.reset}>Atur ulang workflow</button><button className="button secondary" onClick={this.back}>Kembali ke proyek</button></div>
    </main>;
  }
}
