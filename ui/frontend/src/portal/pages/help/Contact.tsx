import { Mail, Bug, Send, MessageSquare } from 'lucide-react';

export default function HelpContact() {
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex items-center gap-3">
        <Mail size={28} className="text-[var(--accent-green)]" />
        <h1 className="text-3xl font-bold">Contact Support</h1>
      </div>

      <div className="space-y-6">
        <p className="text-sm text-[var(--text-secondary)]">
          Have a question, found a bug, or want to share feedback? We'd like to hear from you.
        </p>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <Mail size={14} className="text-[var(--accent-blue)]" />
              Email
            </h2>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              For general questions and support requests.
            </p>
            <p className="mt-2 text-sm text-[var(--accent-blue)]">support@tradingbuddy.app</p>
          </div>

          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <Bug size={14} className="text-[var(--accent-red)]" />
              Bug Reports
            </h2>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              Found something broken? Let us know with as much detail as possible.
            </p>
            <p className="mt-2 text-sm text-[var(--accent-blue)]">bugs@tradingbuddy.app</p>
          </div>
        </div>

        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <MessageSquare size={14} className="text-[var(--accent-blue)]" />
            Send a Message
          </h2>
          <form className="space-y-3" onSubmit={(e) => e.preventDefault()}>
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Subject</label>
              <input type="text" className="form-input" placeholder="What's this about?" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Message</label>
              <textarea className="form-input resize-none" rows={5} placeholder="Describe your question or issue..." />
            </div>
            <button
              type="submit"
              className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent-blue)] px-5 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              <Send size={14} />
              Send Message
            </button>
          </form>
        </div>

        <div className="text-xs text-[var(--text-secondary)]">
          We typically respond within 24 hours on business days.
        </div>
      </div>
    </div>
  );
}
