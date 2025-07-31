import { Bot, Upload, Image as ImageIcon, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useState, useRef } from "react";

interface Model {
  name: string;
  description: string;
  image_url?: string;
  system_prompt?: string;
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
  openGalleryModal: () => void;
  handleImageUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
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
  openGalleryModal,
  handleImageUpload,
  handleUpdateModel
}: SettingsTabProps) {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    handleImageUpload(event);
    setIsDropdownOpen(false);
  };

  const handleGallerySelect = () => {
    openGalleryModal();
    setIsDropdownOpen(false);
  };

  return (
    <div className="space-y-6">
      {/* 기본 정보 카드 */}
      <Card className="bg-white shadow-sm border border-gray-200">
        <CardHeader className="pb-4">
          <div className="flex items-center space-x-3">
            <img src="/favicon.ico" alt="AI Influencer" className="h-10 w-10" />
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
            <div className="flex flex-col items-center justify-center space-y-4 h-full min-h-[300px]">
              {/* 대형 프로필 이미지 - 드롭다운 메뉴 */}
              <DropdownMenu open={isDropdownOpen} onOpenChange={setIsDropdownOpen}>
                <DropdownMenuTrigger asChild>
                  <div className="relative cursor-pointer">
                    {uploadedImage && imagePreview ? (
                      // 업로드된 이미지 미리보기
                      <div className="w-52 h-52 rounded-full overflow-hidden shadow-lg hover:opacity-80 transition-opacity">
                        <img
                          src={imagePreview}
                          alt="Uploaded"
                          className="w-full h-full object-cover"
                        />
                      </div>
                    ) : model?.image_url ? (
                      // 기존 인플루언서 이미지
                      <div className="w-52 h-52 rounded-full overflow-hidden shadow-lg hover:opacity-80 transition-opacity">
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
                                <div class="w-52 h-52 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg">
                                  <div class="w-32 h-32 bg-orange-500 rounded-lg flex items-center justify-center">
                                    <svg class="h-16 w-16 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
                      <div className="w-52 h-52 rounded-full bg-gradient-to-br from-blue-200 to-blue-50 flex items-center justify-center shadow-lg hover:opacity-80 transition-opacity">
                        <img src="/favicon.ico" alt="AI Influencer" className="h-28 w-28" />
                      </div>
                    )}
                    {/* 클릭 안내 오버레이 */}
                    <div className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity bg-black bg-opacity-30 rounded-full">
                      <div className="text-center">
                        <span className="text-white text-sm font-medium">
                          이미지 변경
                        </span>
                      </div>
                    </div>
                  </div>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="center" className="w-48">
                  <DropdownMenuItem 
                    onClick={() => fileInputRef.current?.click()}
                    className="cursor-pointer"
                  >
                    <Upload className="h-4 w-4 mr-2" />
                    파일 업로드
                  </DropdownMenuItem>
                  <DropdownMenuItem 
                    onClick={handleGallerySelect}
                    className="cursor-pointer"
                  >
                    <ImageIcon className="h-4 w-4 mr-2" />
                    갤러리에서 불러오기
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              {/* 숨겨진 파일 입력 */}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileUpload}
                className="hidden"
              />

              <div className="text-center space-y-3">
                <p className="text-sm text-gray-500">
                  권장 크기: 400x400px, 최대 5MB
                </p>
                <p className="text-xs text-gray-400">
                  이미지를 클릭하여 변경
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
                <div>
                  <Label
                    htmlFor="model-system-prompt"
                    className="text-sm font-medium text-gray-700 mb-2 block"
                  >
                    시스템 프롬프트
                  </Label>
                  <Textarea
                    id="model-system-prompt"
                    value={
                      isModelLoading ? "로딩 중..." : model.system_prompt || ""
                    }
                    onChange={(e) =>
                      setModel((prev: any) => ({
                        ...prev,
                        system_prompt: e.target.value,
                      }))
                    }
                    rows={6}
                    placeholder="AI 인플루언서의 성격과 행동을 정의하는 시스템 프롬프트를 입력하세요"
                    className="border-gray-300 focus:border-blue-500 focus:ring-blue-500 resize-none"
                    disabled={isModelLoading}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    시스템 프롬프트는 AI 인플루언서의 기본 성격과 대화 스타일을 결정합니다.
                  </p>
                </div>
              </div>
              <Button
                onClick={handleUpdateModel}
                disabled={
                  isUpdating || isModelLoading || isUploadingImage
                }
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5"
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