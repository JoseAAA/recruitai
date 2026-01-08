import { DashboardLayout } from "@/components/layout/dashboard-layout";
import SettingsPage from "@/components/settings/SettingsPage";

export default function SettingsRoute() {
    return (
        <DashboardLayout>
            <SettingsPage />
        </DashboardLayout>
    );
}
