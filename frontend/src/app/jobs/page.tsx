import { DashboardLayout } from "@/components/layout/dashboard-layout";
import JobsList from "@/components/jobs/JobsList";

export default function JobsPage() {
    return (
        <DashboardLayout>
            <JobsList />
        </DashboardLayout>
    );
}
