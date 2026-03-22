import { DashboardLayout } from "@/components/layout/dashboard-layout";
import JobDetail from "@/components/jobs/JobDetail";

export default function JobDetailPage({ params }: { params: { id: string } }) {
    return (
        <DashboardLayout>
            <JobDetail jobId={params.id} />
        </DashboardLayout>
    );
}
