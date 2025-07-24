import React from "react";
import { RefreshCw, BarChart3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface AnalyticsData {
  totalApiCalls: number;
  todayApiCalls: number;
  publishedPosts: number;
  totalLikes: number;
}

interface WeeklyChartData {
  date: string;
  calls: number;
}

interface PlatformStats {
  name: string;
  posts: number;
  totalLikes: number;
  totalComments: number;
  avgEngagement: number;
  color: string;
}

interface AnalyticsTabProps {
  model: {
    name: string;
  } | null;
  analyticsData: AnalyticsData;
  weeklyChartData: WeeklyChartData[];
  platformStats: Record<string, PlatformStats>;
  isPostsLoading: boolean;
  loadAnalyticsData: () => void;
  getPlatformBadge: (platformName: string) => React.ReactElement;
}

export default function AnalyticsTab({
  model,
  analyticsData,
  weeklyChartData,
  platformStats,
  isPostsLoading,
  loadAnalyticsData,
  getPlatformBadge
}: AnalyticsTabProps) {
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            인플루언서 분석
          </h3>
          <p className="text-sm text-gray-600">
            {model?.name}의 성과와 통계를 확인하세요
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={loadAnalyticsData}
          disabled={isPostsLoading}
          className="flex items-center space-x-2"
        >
          <RefreshCw
            className={`h-4 w-4 ${isPostsLoading ? "animate-spin" : ""}`}
          />
          <span>새로고침</span>
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
        <Card>
          <CardContent className="p-6">
            <div className="text-center">
              <p className="text-2xl font-bold text-blue-600">
                {analyticsData.totalApiCalls.toLocaleString()}
              </p>
              <p className="text-sm text-gray-600">총 API 호출</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="text-center">
              <p className="text-2xl font-bold text-orange-600">
                {analyticsData.todayApiCalls.toLocaleString()}
              </p>
              <p className="text-sm text-gray-600">오늘 호출</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="text-center">
              <p className="text-2xl font-bold text-green-600">
                {analyticsData.publishedPosts.toLocaleString()}
              </p>
              <p className="text-sm text-gray-600">발행된 게시글</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="text-center">
              <p className="text-2xl font-bold text-purple-600">
                {analyticsData.totalLikes.toLocaleString()}
              </p>
              <p className="text-sm text-gray-600">총 좋아요</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>사용량 통계</CardTitle>
          <CardDescription>
            최근 7일간의 API 사용량 추이입니다
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            {weeklyChartData.length > 0 ? (
              <div className="h-full flex items-end justify-between space-x-2">
                {weeklyChartData.map((data, index) => (
                  <div
                    key={data.date}
                    className="flex-1 flex flex-col items-center"
                  >
                    <div
                      className="w-full bg-blue-500 rounded-t"
                      style={{
                        height: `${Math.max((data.calls / Math.max(...weeklyChartData.map((d) => d.calls))) * 200, 4)}px`,
                      }}
                    />
                    <div className="text-xs text-gray-500 mt-2 text-center">
                      {new Date(data.date).toLocaleDateString("ko-KR", {
                        month: "short",
                        day: "numeric",
                      })}
                    </div>
                    <div className="text-xs font-medium text-gray-700 mt-1">
                      {data.calls}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="h-full flex items-center justify-center">
                <div className="text-center">
                  <BarChart3 className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                  <p className="text-gray-500 mb-2">
                    차트 데이터 로딩 중...
                  </p>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>플랫폼별 성과 요약</CardTitle>
          <CardDescription>
            각 소셜미디어 플랫폼별 게시글 성과를 확인하세요
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Object.values(platformStats).map((stats) => (
              <div
                key={stats.name}
                className="bg-white border rounded-lg p-4"
              >
                <div className="flex items-center space-x-3 mb-4">
                  <div
                    className={`w-3 h-3 rounded-full ${stats.color}`}
                  ></div>
                  <h4 className="font-semibold text-gray-900">
                    {stats.name}
                  </h4>
                  {getPlatformBadge(stats.name)}
                </div>

                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">
                      게시글 수
                    </span>
                    <span className="font-medium">{stats.posts}개</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">
                      총 좋아요
                    </span>
                    <span className="font-medium">
                      {stats.totalLikes.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">총 댓글</span>
                    <span className="font-medium">
                      {stats.totalComments.toLocaleString()}
                    </span>
                  </div>

                  <div className="flex justify-between border-t pt-2">
                    <span className="text-sm text-gray-600">
                      평균 참여
                    </span>
                    <span className="font-semibold text-blue-600">
                      {stats.avgEngagement.toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}