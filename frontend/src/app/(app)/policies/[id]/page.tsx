import { redirect } from "next/navigation";
interface Props { params: Promise<{ id: string }>; }
export default async function OldPolicyDetailRedirect({ params }: Props) {
  const { id } = await params;
  redirect(`/app/policies/${id}`);
}
