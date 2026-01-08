"use client";

import {
    RadarChart,
    PolarGrid,
    PolarAngleAxis,
    PolarRadiusAxis,
    Radar,
    ResponsiveContainer,
    Legend,
} from "recharts";

interface RadarDataPoint {
    axis: string;
    candidate: number;
    ideal: number;
}

interface RadarComparisonProps {
    candidateName: string;
    data: RadarDataPoint[];
}

export function RadarComparison({ candidateName, data }: RadarComparisonProps) {
    return (
        <div className="w-full h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={data} margin={{ top: 20, right: 30, bottom: 20, left: 30 }}>
                    <PolarGrid
                        stroke="hsl(217.2 32.6% 25%)"
                        strokeDasharray="3 3"
                    />
                    <PolarAngleAxis
                        dataKey="axis"
                        tick={{ fill: "hsl(215 20.2% 65.1%)", fontSize: 11 }}
                        tickLine={{ stroke: "hsl(217.2 32.6% 25%)" }}
                    />
                    <PolarRadiusAxis
                        angle={90}
                        domain={[0, 100]}
                        tick={{ fill: "hsl(215 20.2% 65.1%)", fontSize: 10 }}
                        axisLine={{ stroke: "hsl(217.2 32.6% 25%)" }}
                    />
                    {/* Ideal Profile */}
                    <Radar
                        name="Ideal Profile"
                        dataKey="ideal"
                        stroke="hsl(217.2 91.2% 59.8%)"
                        fill="hsl(217.2 91.2% 59.8%)"
                        fillOpacity={0.1}
                        strokeWidth={2}
                        strokeDasharray="5 5"
                    />
                    {/* Candidate Profile */}
                    <Radar
                        name={candidateName}
                        dataKey="candidate"
                        stroke="hsl(142 76% 46%)"
                        fill="hsl(142 76% 46%)"
                        fillOpacity={0.3}
                        strokeWidth={2}
                    />
                    <Legend
                        wrapperStyle={{
                            paddingTop: "10px",
                            fontSize: "12px",
                        }}
                    />
                </RadarChart>
            </ResponsiveContainer>
        </div>
    );
}
