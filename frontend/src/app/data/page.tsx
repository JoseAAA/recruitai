import { Suspense } from "react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import DataIngestion from "@/components/data/DataIngestion";

export default function DataIngestionPage() {
    return (
        <DashboardLayout>
            <Suspense>
                <DataIngestion />
            </Suspense>
        </DashboardLayout>
    );
}
