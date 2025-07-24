import { 
  Upload, 
  CheckCircle, 
  PlayCircle, 
  PauseCircle, 
  Mic, 
  Volume2, 
  AlertCircle, 
  Loader2, 
  RefreshCw, 
  Download, 
  Trash2 
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

interface Voice {
  id: string;
  text: string;
  createdAt: string;
  status?: string;
  url?: string;
  duration?: number;
}

interface VoiceTabProps {
  hasBaseVoice: boolean;
  baseVoiceUrl?: string | null;
  baseVoiceFile: File | null;
  isUploadingBaseVoice: boolean;
  voiceText: string;
  isGeneratingVoice: boolean;
  voiceHistory: Voice[];
  isLoadingVoiceHistory: boolean;
  playingVoiceUrl: string | null;
  setBaseVoiceFile: (file: File | null) => void;
  setVoiceText: (text: string) => void;
  setVoiceToDelete: (id: string) => void;
  handlePlayVoice: (url: string) => void;
  handleChangeBaseVoice: () => void;
  handleBaseVoiceFileSelect: (event: React.ChangeEvent<HTMLInputElement>) => void;
  handleUploadBaseVoice: () => void;
  handleGenerateVoice: () => void;
  loadVoiceHistory: () => void;
  handleDownloadVoice: (url: string, id: string) => void;
  toast: (options: { title: string; description: string; variant?: "destructive" }) => void;
}

export default function VoiceTab({
  hasBaseVoice,
  baseVoiceUrl,
  baseVoiceFile,
  isUploadingBaseVoice,
  voiceText,
  isGeneratingVoice,
  voiceHistory,
  isLoadingVoiceHistory,
  playingVoiceUrl,
  setBaseVoiceFile,
  setVoiceText,
  setVoiceToDelete,
  handlePlayVoice,
  handleChangeBaseVoice,
  handleBaseVoiceFileSelect,
  handleUploadBaseVoice,
  handleGenerateVoice,
  loadVoiceHistory,
  handleDownloadVoice,
  toast
}: VoiceTabProps) {
  return (
    <div className="space-y-6">
      {/* 베이스 음성 업로드 카드 */}
      <Card className="bg-white shadow-sm border border-gray-200">
        <CardHeader className="pb-4">
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 bg-indigo-100 rounded-lg flex items-center justify-center">
              <Upload className="h-6 w-6 text-indigo-600" />
            </div>
            <div>
              <CardTitle className="text-lg font-medium text-gray-900">
                베이스 음성 설정
              </CardTitle>
              <CardDescription className="text-sm text-gray-600 mt-1">
                AI 인플루언서의 목소리가 될 기본 음성을 업로드하세요.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {hasBaseVoice ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-center space-x-3">
                  <CheckCircle className="h-5 w-5 text-green-600" />
                  <div>
                    <p className="text-sm font-medium text-green-900">
                      베이스 음성이 설정되었습니다
                    </p>
                    <p className="text-xs text-green-700 mt-1">
                      이제 텍스트를 음성으로 변환할 수 있습니다.
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  {baseVoiceUrl && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handlePlayVoice(baseVoiceUrl)}
                    >
                      {playingVoiceUrl === baseVoiceUrl ? (
                        <PauseCircle className="h-4 w-4" />
                      ) : (
                        <PlayCircle className="h-4 w-4" />
                      )}
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleChangeBaseVoice}
                    className="text-indigo-600 hover:text-indigo-700"
                  >
                    변경
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                <input
                  type="file"
                  accept="audio/*"
                  onChange={handleBaseVoiceFileSelect}
                  className="hidden"
                  id="base-voice-upload"
                />
                <label
                  htmlFor="base-voice-upload"
                  className="cursor-pointer"
                >
                  <Upload className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                  <p className="text-sm font-medium text-gray-900 mb-1">
                    클릭하여 음성 파일 선택
                  </p>
                  <p className="text-xs text-gray-500">
                    MP3, WAV, M4A 등 (최대 10MB)
                  </p>
                </label>
              </div>
              {baseVoiceFile && (
                <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center space-x-3">
                    <Volume2 className="h-5 w-5 text-gray-600" />
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {baseVoiceFile.name}
                      </p>
                      <p className="text-xs text-gray-500">
                        {(baseVoiceFile.size / 1024 / 1024).toFixed(2)}{" "}
                        MB
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setBaseVoiceFile(null);
                      }}
                    >
                      취소
                    </Button>
                    <Button
                      size="sm"
                      onClick={handleUploadBaseVoice}
                      disabled={isUploadingBaseVoice}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white"
                    >
                      {isUploadingBaseVoice ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          업로드 중...
                        </>
                      ) : (
                        "업로드"
                      )}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 음성 생성 카드 */}
      <Card
        className={`bg-white shadow-sm border border-gray-200 ${!hasBaseVoice ? "opacity-50" : ""}`}
      >
        <CardHeader className="pb-4">
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
              <Mic className="h-6 w-6 text-purple-600" />
            </div>
            <div>
              <CardTitle className="text-lg font-medium text-gray-900">
                음성 생성
              </CardTitle>
              <CardDescription className="text-sm text-gray-600 mt-1">
                텍스트를 입력하면 AI 인플루언서의 음성으로 변환할 수
                있습니다.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {!hasBaseVoice && (
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-sm text-yellow-800">
                <AlertCircle className="h-4 w-4 inline mr-1" />
                먼저 베이스 음성을 업로드해주세요.
              </p>
            </div>
          )}
          <div>
            <Label htmlFor="voice-text">텍스트 입력</Label>
            <Textarea
              id="voice-text"
              placeholder="음성으로 변환할 텍스트를 입력하세요..."
              className="min-h-[100px] mt-2"
              value={voiceText}
              onChange={(e) => {
                const newText = e.target.value;
                if (newText.length <= 300) {
                  setVoiceText(newText);
                } else {
                  toast({
                    title: "글자수 제한",
                    description:
                      "텍스트는 300자까지만 입력할 수 있습니다.",
                    variant: "destructive",
                  });
                }
              }}
              disabled={!hasBaseVoice}
              maxLength={300}
            />
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-500">
              {voiceText.length} / 300자
            </span>
            <Button
              onClick={handleGenerateVoice}
              disabled={
                !hasBaseVoice ||
                !voiceText.trim() ||
                isGeneratingVoice ||
                voiceText.length > 300
              }
              className="bg-purple-600 hover:bg-purple-700 text-white"
            >
              {isGeneratingVoice ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  생성 중...
                </>
              ) : (
                <>
                  <Volume2 className="h-4 w-4 mr-2" />
                  음성 생성
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 생성된 음성 목록 카드 */}
      <Card className="bg-white shadow-sm border border-gray-200">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                <Volume2 className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <CardTitle className="text-lg font-medium text-gray-900">
                  생성된 음성
                </CardTitle>
                <CardDescription className="text-sm text-gray-600 mt-1">
                  이전에 생성한 음성 파일들을 관리할 수 있습니다.
                </CardDescription>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={loadVoiceHistory}
              disabled={isLoadingVoiceHistory}
              className="flex items-center space-x-2"
            >
              <RefreshCw
                className={`h-4 w-4 ${isLoadingVoiceHistory ? "animate-spin" : ""}`}
              />
              <span>새로고침</span>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {isLoadingVoiceHistory ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600 mx-auto mb-4"></div>
              <p className="text-gray-500">
                음성 목록을 불러오는 중...
              </p>
            </div>
          ) : voiceHistory.length > 0 ? (
            <div className="space-y-3">
              {voiceHistory.map((voice) => (
                <div
                  key={voice.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center space-x-3">
                    {voice.status === "pending" ? (
                      <div className="p-2 bg-yellow-100 rounded-full">
                        <Loader2 className="h-5 w-5 text-yellow-600 animate-spin" />
                      </div>
                    ) : voice.status === "failed" ? (
                      <div className="p-2 bg-red-100 rounded-full">
                        <AlertCircle className="h-5 w-5 text-red-600" />
                      </div>
                    ) : (
                      <button
                        onClick={() => handlePlayVoice(voice.url!)}
                        className="p-2 bg-white rounded-full shadow-sm hover:shadow-md transition-shadow"
                        disabled={!voice.url}
                      >
                        {playingVoiceUrl === voice.url ? (
                          <PauseCircle className="h-5 w-5 text-purple-600" />
                        ) : (
                          <PlayCircle className="h-5 w-5 text-purple-600" />
                        )}
                      </button>
                    )}
                    <div>
                      <p className="text-sm font-medium text-gray-900 line-clamp-1">
                        {voice.text}
                      </p>
                      <p className="text-xs text-gray-500">
                        {new Date(voice.createdAt).toLocaleDateString(
                          "ko-KR",
                        )}{" "}
                        •{" "}
                        {voice.status === "pending"
                          ? "생성 중..."
                          : voice.status === "failed"
                            ? "생성 실패"
                            : voice.duration
                              ? `${voice.duration}초`
                              : "길이 정보 없음"}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        handleDownloadVoice(voice.url!, voice.id)
                      }
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setVoiceToDelete(voice.id)}
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <Volume2 className="h-12 w-12 mx-auto mb-4 text-gray-300" />
              <p className="text-gray-500 text-lg">
                아직 생성된 음성이 없습니다
              </p>
              <p className="text-gray-400 mt-2">
                위에서 텍스트를 입력하고 음성을 생성해보세요!
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}