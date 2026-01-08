import { DashboardLayout } from "@/components/layout/dashboard-layout";
import CreateVacancy from "@/components/jobs/CreateVacancy";

export default function NewJobPage() {
    return (
        <DashboardLayout>
            <CreateVacancy />
        </DashboardLayout>
    );
}
