import { DashboardLayout } from "@/components/layout/dashboard-layout";
import CandidateList from "@/components/candidates/CandidateList";

export default function CandidatesPage() {
    return (
        <DashboardLayout>
            <CandidateList />
        </DashboardLayout>
    );
}
