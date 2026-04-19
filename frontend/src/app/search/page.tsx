import { redirect } from "next/navigation";

// Search route removed — no nav entry points to it.
// Redirect to jobs list to avoid 404 on any bookmarked URLs.
export default function SearchPage() {
    redirect("/jobs");
}
