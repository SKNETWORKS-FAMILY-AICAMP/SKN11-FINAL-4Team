import { 
  Instagram, 
  CheckCircle, 
  AlertCircle, 
  RefreshCw, 
  Unlink 
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

interface InstagramInfo {
  username?: string;
  account_type?: string;
  name?: string;
  biography?: string;
  website?: string;
  followers_count?: number;
  follows_count?: number;
  media_count?: number;
  profile_picture_url?: string;
}

interface InstagramStatus {
  is_connected: boolean;
  token_expired?: boolean;
  connected_at?: string;
  instagram_info?: InstagramInfo;
}

interface IntegrationsTabProps {
  instagramStatus: InstagramStatus;
  isConnecting: boolean;
  handleInstagramConnect: () => void;
  handleInstagramDisconnect: () => void;
  PostImage: React.ComponentType<{
    url: string;
    alt: string;
    className: string;
  }>;
}

export default function IntegrationsTab({
  instagramStatus,
  isConnecting,
  handleInstagramConnect,
  handleInstagramDisconnect,
  PostImage
}: IntegrationsTabProps) {

  return (
    <div className="space-y-6">
      {/* Instagram 계정 연동 */}
      <Card className="bg-white shadow-sm border border-gray-200">
        <CardHeader className="pb-4">
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 bg-pink-100 rounded-lg flex items-center justify-center">
              <Instagram className="h-6 w-6 text-pink-600" />
            </div>
            <div>
              <CardTitle className="text-lg font-medium text-gray-900">
                Instagram 계정 연동
              </CardTitle>
              <CardDescription className="text-sm text-gray-600 mt-1">
                비즈니스 계정을 연동하여 AI 콘텐츠 자동 포스팅, 인사이트
                분석 등 다양한 기능을 활용하세요.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {instagramStatus.is_connected ? (
            <div className="space-y-6">
              {/* 연동된 계정 정보 */}
              <div
                className={`flex items-start space-x-4 p-4 rounded-lg border-2 ${instagramStatus.token_expired
                  ? "bg-yellow-50 border-yellow-200"
                  : "bg-green-50 border-green-200"
                  }`}
              >
                <div className="w-12 h-12 bg-gradient-to-br from-pink-500 to-purple-600 rounded-full flex items-center justify-center shadow-sm">
                  {instagramStatus.instagram_info
                    ?.profile_picture_url ? (
                    <PostImage
                      url={
                        instagramStatus.instagram_info
                          .profile_picture_url
                      }
                      alt="Profile"
                      className="w-12 h-12 rounded-full object-cover"
                    />
                  ) : (
                    <Instagram className="h-6 w-6 text-white" />
                  )}
                </div>
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-1">
                    {instagramStatus.token_expired ? (
                      <AlertCircle className="h-4 w-4 text-yellow-600" />
                    ) : (
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    )}
                    <p
                      className={`font-medium ${instagramStatus.token_expired
                        ? "text-yellow-900"
                        : "text-green-900"
                        }`}
                    >
                      {instagramStatus.token_expired
                        ? "Instagram 계정 재연동 필요"
                        : "Instagram 계정 연동됨"}
                    </p>
                  </div>
                  <p
                    className={`text-sm ${instagramStatus.token_expired
                      ? "text-yellow-700"
                      : "text-green-700"
                      }`}
                  >
                    @
                    {instagramStatus.instagram_info?.username ||
                      "Unknown"}{" "}
                    •{" "}
                    {instagramStatus.instagram_info?.account_type ||
                      "Unknown"}{" "}
                    계정
                  </p>
                  {instagramStatus.connected_at && (
                    <p
                      className={`text-xs mt-1 ${instagramStatus.token_expired
                        ? "text-yellow-600"
                        : "text-green-600"
                        }`}
                    >
                      연동일:{" "}
                      {new Date(
                        instagramStatus.connected_at,
                      ).toLocaleDateString("ko-KR")}
                    </p>
                  )}
                </div>
              </div>

              {/* Instagram 상세 정보 */}
              <div className="space-y-4">
                {/* 통계 정보 */}
                <div className="grid grid-cols-3 gap-4 p-4 bg-white rounded-lg border border-gray-200">
                  <div className="text-center">
                    <p className="text-lg font-semibold text-gray-900">
                      {(
                        instagramStatus.instagram_info
                          ?.followers_count || 0
                      ).toLocaleString()}
                    </p>
                    <p className="text-xs text-gray-500">팔로워</p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-semibold text-gray-900">
                      {(
                        instagramStatus.instagram_info
                          ?.follows_count || 0
                      ).toLocaleString()}
                    </p>
                    <p className="text-xs text-gray-500">팔로잉</p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-semibold text-gray-900">
                      {(
                        instagramStatus.instagram_info
                          ?.media_count || 0
                      ).toLocaleString()}
                    </p>
                    <p className="text-xs text-gray-500">게시물</p>
                  </div>
                </div>

                {/* 프로필 정보 */}
                {instagramStatus.instagram_info && (
                  instagramStatus.instagram_info.name ||
                  instagramStatus.instagram_info.biography ||
                  instagramStatus.instagram_info.website
                ) && (
                  <div className="p-4 bg-white rounded-lg border border-gray-200 space-y-3">
                    {instagramStatus.instagram_info.name && (
                      <div>
                        <p className="text-xs text-gray-500 mb-1">
                          이름
                        </p>
                        <p className="text-sm font-medium text-gray-900">
                          {instagramStatus.instagram_info.name}
                        </p>
                      </div>
                    )}

                    {instagramStatus.instagram_info.biography && (
                      <div>
                        <p className="text-xs text-gray-500 mb-1">
                          소개
                        </p>
                        <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                          {instagramStatus.instagram_info.biography}
                        </p>
                      </div>
                    )}

                    {instagramStatus.instagram_info.website && (
                      <div>
                        <p className="text-xs text-gray-500 mb-1">
                          웹사이트
                        </p>
                        <a
                          href={
                            instagramStatus.instagram_info.website
                          }
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-blue-600 hover:text-blue-800 underline"
                        >
                          {instagramStatus.instagram_info.website}
                        </a>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* 재연동/연동 해제 버튼 */}
              <div className="pt-2 space-y-3">
                {instagramStatus.token_expired && (
                  <Button
                    onClick={handleInstagramConnect}
                    disabled={isConnecting}
                    className="w-full bg-yellow-500 hover:bg-yellow-600 text-white font-medium py-2.5"
                  >
                    {isConnecting ? (
                      <>
                        <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                        재연동 중...
                      </>
                    ) : (
                      <>
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Instagram 계정 재연동하기
                      </>
                    )}
                  </Button>
                )}
                <Button
                  variant="outline"
                  onClick={handleInstagramDisconnect}
                  className="w-full text-red-600 border-red-200 hover:bg-red-50 font-medium py-2.5"
                >
                  <Unlink className="h-4 w-4 mr-2" />
                  연동 해제
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {/* 연동 버튼 */}
              <Button
                onClick={handleInstagramConnect}
                disabled={isConnecting}
                className="w-full bg-gradient-to-r from-pink-500 to-purple-600 hover:from-pink-600 hover:to-purple-700 text-white font-medium py-3 text-base"
              >
                {isConnecting ? (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    연동 중...
                  </>
                ) : (
                  "Instagram 계정 연동하기"
                )}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}