import { ChatWindow } from "@/components/ChatWindow";

export default function Home() {
  return (
    <main className="container">
      <header className="header">
        <h1>CCU Diagnostic Agent</h1>
        <p>Describe an incident in natural language. The agent will diagnose, report, and notify — no automatic action is executed.</p>
      </header>
      <ChatWindow />
    </main>
  );
}
