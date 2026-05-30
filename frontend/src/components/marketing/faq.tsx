"use client";

import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";

const faqs = [
  {
    q: "What types of insurance policies can I manage in sVault?",
    a: "sVault supports all corporate insurance categories: Vehicle, Machinery, Plant, Factory/Property, Employees Group Health, Key Person, Stock (Raw Material & Finished Goods), and a catch-all Other category. More policy types can be configured for Enterprise plans.",
  },
  {
    q: "How does the 14-day free trial work?",
    a: "Sign up with Google or email — no credit card required. You get full Professional plan access for 14 days. At the end of the trial, choose a plan or drop to Free. Your data is always yours and exportable.",
  },
  {
    q: "Which alert channels are supported?",
    a: "WhatsApp (approved utility templates), SMS (TRAI DLT-compliant transactional templates), Email (HTML + plain text), and Telegram. Alerts fire at 60, 30, 15, 7, and 1 day before expiry, with escalation to managers if not acknowledged.",
  },
  {
    q: "Is sVault compliant with India's DPDP Act?",
    a: "Yes. sVault is designed to comply with the Digital Personal Data Protection Act 2023. Data is stored in India, encrypted at rest, access-controlled by Role-Level Security, and we maintain a 1-year audit log. We treat your data as a Data Fiduciary.",
  },
  {
    q: "Can I manage multiple companies or subsidiaries?",
    a: "Yes. The Professional and Enterprise plans support multi-org hierarchies. Parent-company admins see a consolidated group dashboard, while subsidiary users are scoped to their own org. Cross-subsidiary access is permission-controlled.",
  },
  {
    q: "What is 'Ask sVault' (AI)?",
    a: "Ask sVault is an AI-powered RAG (Retrieval-Augmented Generation) interface over your policy documents. Ask natural-language questions like 'What is the claim excess for our fleet policy?' and get precise answers from the actual document text — not generic AI answers.",
  },
  {
    q: "Can I use sVault's API to integrate with our ERP or HRMS?",
    a: "Yes. Professional and Enterprise plans include a developer API with scoped, hashed API keys and signed outbound webhooks. Integrate renewal alerts or policy data into your existing systems.",
  },
  {
    q: "How do I migrate from Excel?",
    a: "You can import policies manually via the web UI, or use the API to bulk-import from a structured CSV. We provide an import template and onboarding support on paid plans.",
  },
];

export function FaqSection() {
  return (
    <section
      className="bg-zinc-50 py-20 dark:bg-zinc-900"
      aria-labelledby="faq-heading"
    >
      <div className="mx-auto max-w-3xl px-4 sm:px-6">
        <div className="text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-brand-600">
            FAQ
          </p>
          <h2
            id="faq-heading"
            className="mt-2 text-3xl font-bold tracking-tight text-zinc-900 dark:text-white sm:text-4xl"
          >
            Common questions
          </h2>
        </div>

        <Accordion type="single" collapsible className="mt-10">
          {faqs.map((faq, i) => (
            <AccordionItem key={i} value={`item-${i}`}>
              <AccordionTrigger className="text-left text-zinc-900 dark:text-white">
                {faq.q}
              </AccordionTrigger>
              <AccordionContent className="text-zinc-600 dark:text-zinc-400">
                {faq.a}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
}
