import { Bot } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

interface Model {
  name: string;
  description: string;
  image_url?: string;
}

interface SettingsTabProps {
  model: Model;
  setModel: React.Dispatch<React.SetStateAction<any>>;
  isModelLoading: boolean;
  uploadedImage: File | null;
  imagePreview: string | null;
  isUpdating: boolean;
  isUploadingImage: boolean;
  openImageModal: () => void;
  handleUpdateModel: () => void;
}

export default function SettingsTab({
  model,
  setModel,
  isModelLoading,
  uploadedImage,
  imagePreview,
  isUpdating,
  isUploadingImage,
  openImageModal,
  handleUpdateModel
}: SettingsTabProps) {
  return (
    <div className="space-y-6">
      {/* 기본 정보 카드 */}
      <Card className="bg-white shadow-sm border border-gray-200">
        <CardHeader className="pb-4">
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <Bot className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <CardTitle className="text-lg font-medium text-gray-900">
                기본 정보
              </CardTitle>
              <CardDescription className="text-sm text-gray-600 mt-1">
                AI 인플루언서의 프로필 이미지를 설정하고 기본 정보를
                수정할 수 있습니다.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-8">
          {/* 프로필 이미지와 기본 정보를 가로로 배치 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* 프로필 이미지 섹션 */}
            <div className="flex flex-col items-center space-y-4 pt-12">
              {/* 대형 프로필 이미지 - 클릭 가능 */}
              <div
                className="relative cursor-pointer"
                onClick={openImageModal}
              >
                {uploadedImage && imagePreview ? (
                  // 업로드된 이미지 미리보기
                  <div className="w-36 h-36 rounded-full overflow-hidden shadow-lg hover:opacity-80 transition-opacity">
                    <img
                      src={imagePreview}
                      alt="Uploaded"
                      className="w-full h-full object-cover"
                    />
                  </div>
                ) : model?.image_url ? (
                  // 기존 인플루언서 이미지
                  <div className="w-36 h-36 rounded-full overflow-hidden shadow-lg hover:opacity-80 transition-opacity">
                    <img
                      src={model.image_url}
                      alt="Profile"
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        // 이미지 로드 실패 시 기본 아이콘 표시
                        const target = e.target as HTMLImageElement;
                        target.style.display = "none";
                        const parent = target.parentElement;
                        if (parent) {
                          parent.innerHTML = `
                            <div class="w-36 h-36 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg">
                              <div class="w-20 h-20 bg-orange-500 rounded-lg flex items-center justify-center">
                                <svg class="h-10 w-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                                </svg>
                              </div>
                            </div>
                          `;
                        }
                      }}
                    />
                  </div>
                ) : (
                  // 기본 아이콘
                  <div className="w-36 h-36 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg hover:opacity-80 transition-opacity">
                    <div className="w-20 h-20 bg-orange-500 rounded-lg flex items-center justify-center">
                      <Bot className="h-10 w-10 text-white" />
                    </div>
                  </div>
                )}
                {/* 클릭 안내 오버레이 */}
                <div className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity bg-black bg-opacity-30 rounded-full">
                  <div className="text-center">
                    <span className="text-white text-sm font-medium">
                      확대/변경
                    </span>
                  </div>
                </div>
              </div>

              <div className="text-center space-y-3">
                <p className="text-sm text-gray-500">
                  권장 크기: 400x400px, 최대 5MB
                </p>
                <p className="text-xs text-gray-400">
                  이미지를 클릭하여 확대/변경
                </p>
              </div>
            </div>

            {/* 기본 정보 입력 섹션 */}
            <div className="space-y-6">
              <div className="space-y-4">
                <div>
                  <Label
                    htmlFor="model-name"
                    className="text-sm font-medium text-gray-700 mb-2 block"
                  >
                    모델 이름
                  </Label>
                  <Input
                    id="model-name"
                    value={isModelLoading ? "로딩 중..." : model.name}
                    onChange={(e) =>
                      setModel((prev: any) => ({
                        ...prev,
                        name: e.target.value,
                      }))
                    }
                    placeholder="AI 인플루언서 이름을 입력하세요"
                    className="border-gray-300 focus:border-blue-500 focus:ring-blue-500"
                    disabled={isModelLoading}
                  />
                </div>
                <div>
                  <Label
                    htmlFor="model-description"
                    className="text-sm font-medium text-gray-700 mb-2 block"
                  >
                    설명
                  </Label>
                  <Textarea
                    id="model-description"
                    value={
                      isModelLoading ? "로딩 중..." : model.description
                    }
                    onChange={(e) =>
                      setModel((prev: any) => ({
                        ...prev,
                        description: e.target.value,
                      }))
                    }
                    rows={4}
                    placeholder="AI 인플루언서에 대한 설명을 입력하세요"
                    className="border-gray-300 focus:border-blue-500 focus:ring-blue-500 resize-none"
                    disabled={isModelLoading}
                  />
                </div>
              </div>
              <Button
                onClick={handleUpdateModel}
                disabled={
                  isUpdating || isModelLoading || isUploadingImage
                }
                className="w-full bg-gray-800 hover:bg-gray-900 text-white font-medium py-2.5"
              >
                {isUploadingImage
                  ? "이미지 업로드 중..."
                  : isUpdating
                    ? "업데이트 중..."
                    : isModelLoading
                      ? "로딩 중..."
                      : "정보 저장"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}