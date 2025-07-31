"use client";

import { useState, Suspense, useEffect, useRef } from "react";
import { AlertCircle } from "lucide-react";
import React, { FC } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Navigation } from "@/components/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import {
  ModelTabsList,
  AnalyticsTab,
  ContentTab,
  ApiTab,
  IntegrationsTab,
  SettingsTab,
  VoiceTab,
  McpTab
} from "./components";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

import { tokenUtils } from "@/lib/auth";
import { ModelService } from "@/lib/services/model.service";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/hooks/use-auth";
import { Toaster } from "@/components/ui/toaster";
import {
  ArrowLeft,
  Copy,
  Eye,
  EyeOff,
  RefreshCw,
  Download,
  BarChart3,
  Info,
  FileText,
  ExternalLink,
  Calendar,
  Heart,
  MessageCircle,
  Play,
  MoreHorizontal,
  Bookmark,
  Bot,
  Clock,
  Trash2,
  Upload,
  MessageSquare,
  Instagram,
  Link2,
  Unlink,
  CheckCircle,
  Users,
  Edit,
  User,
  Settings,
  Mic,
  Volume2,
  PlayCircle,
  PauseCircle,
  Loader2,
  ImageIcon,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import type { AIModel } from "@/lib/types";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { apiClient } from "@/lib/api";
import { PostCard, Post } from "@/components/ui/post-card";
import MCPService from "@/lib/services/mcp.service";
import { galleryService } from "@/lib/services/gallery.service";

// 샘플 모델 데이터
const sampleModel: AIModel = {
  id: "1",
  name: "패션 인플루언서 AI",
  description: "20대 여성 타겟의 패션 트렌드 전문 AI 인플루언서",
  personality: "친근하고 트렌디한",
  tone: "캐주얼하고 친밀한",
  status: "ready",
  createdAt: "2024-01-15",
  apiKey: "ai_inf_1234567890abcdef",
  trainingData: { textSamples: 1500, voiceSamples: 200, imageSamples: 300 },
};

// 샘플 콘텐츠 데이터
type ContentPost = Post;

// 게시글 상세 이미지 apiClient 방식 컴포넌트
function PostImage({
  url,
  alt,
  className,
}: {
  url: string;
  alt?: string;
  className?: string;
}) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!url) return;
    if (!url.startsWith("/uploads/")) {
      setImageUrl(url);
      return;
    }
    apiClient
      .get(url, { requireAuth: false })
      .then((res: any) => {
        if (res.data instanceof Blob) {
          const blobUrl = URL.createObjectURL(res.data);
          setImageUrl(blobUrl);
        } else {
          setImageUrl(url);
        }
      })
      .catch(() => {
        setImageUrl(url);
      });
    return () => {
      if (imageUrl && imageUrl.startsWith("blob:")) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [url]);
  if (!imageUrl)
    return (
      <div className="bg-gray-100 w-full h-80 flex items-center justify-center text-gray-400">
        이미지 불러오는 중...
      </div>
    );
  return <img src={imageUrl} alt={alt} className={className} />;
}

function ModelDetailContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { toast } = useToast();
  const { user } = useAuth();
  const [model, setModel] = useState<any>(null);
  const [imgError, setImgError] = useState(false);
  const [isModelLoading, setIsModelLoading] = useState(true);
  const [posts, setPosts] = useState<ContentPost[]>([]);
  const [isPostsLoading, setIsPostsLoading] = useState(true);
  const [selectedPost, setSelectedPost] = useState<ContentPost | null>(null);
  const [isPostDetailModalOpen, setIsPostDetailModalOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isUploadingImage, setIsUploadingImage] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const [editHashtags, setEditHashtags] = useState("");
  const [editScheduledAt, setEditScheduledAt] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadedImage, setUploadedImage] = useState<File | null>(null);
  const [showApiKey, setShowApiKey] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isGeneratingApiKey, setIsGeneratingApiKey] = useState(false);
  const [apiKeyInfo, setApiKeyInfo] = useState<{
    api_key: string;
    created_at: string;
    updated_at: string;
  } | null>(null);
  const [testMessage, setTestMessage] = useState("");
  const [testResponse, setTestResponse] = useState("");
  const [isTestingChatbot, setIsTestingChatbot] = useState(false);
  const [activeTab, setActiveTab] = useState(() => {
    // URL 파라미터에서 탭 정보 읽기
    return searchParams.get("tab") || "analytics";
  });
  // 음성 관련 상태
  const [voiceText, setVoiceText] = useState("");
  const [isGeneratingVoice, setIsGeneratingVoice] = useState(false);
  const [voiceHistory, setVoiceHistory] = useState<
    Array<{
      id: string;
      text: string;
      url: string;
      s3_url?: string;
      duration?: number;
      createdAt: string;
      status?: string; // pending, completed, failed
    }>
  >([]);
  const [isLoadingVoiceHistory, setIsLoadingVoiceHistory] = useState(false);
  const previousVoiceStatusRef = useRef<Map<string, string>>(new Map());
  const [playingVoiceUrl, setPlayingVoiceUrl] = useState<string | null>(null);
  const [baseVoiceFile, setBaseVoiceFile] = useState<File | null>(null);
  const [baseVoiceUrl, setBaseVoiceUrl] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isUploadingBaseVoice, setIsUploadingBaseVoice] = useState(false);
  const [hasBaseVoice, setHasBaseVoice] = useState(false);
  const [isImageModalOpen, setIsImageModalOpen] = useState(false);
  const [isGalleryModalOpen, setIsGalleryModalOpen] = useState(false);
  const [galleryImages, setGalleryImages] = useState<any[]>([]);
  const [isLoadingGallery, setIsLoadingGallery] = useState(false);
  const [galleryCurrentPage, setGalleryCurrentPage] = useState(1);
  const [galleryTotalPages, setGalleryTotalPages] = useState(1);
  const [galleryTotalImages, setGalleryTotalImages] = useState(0);
  const [hasImageChanges, setHasImageChanges] = useState(false);
  const [voiceToDelete, setVoiceToDelete] = useState<string | null>(null);
  const [instagramStatus, setInstagramStatus] = useState<{
    is_connected: boolean;
    instagram_id?: string;
    instagram_page_id?: string;
    instagram_username?: string;
    instagram_account_type?: string;
    connected_at?: string;
    token_expires_at?: string;
    token_expired?: boolean;
    instagram_info?: {
      id: string;
      username: string;
      account_type: string;
      name?: string;
      biography?: string;
      followers_count?: number;
      follows_count?: number;
      media_count?: number;
      profile_picture_url?: string;
      website?: string;
    };
  }>({
    is_connected: false,
  });
  const [isConnecting, setIsConnecting] = useState(false);
  const [carouselIndices, setCarouselIndices] = useState<{ [key: string]: number }>({});
  const [analyticsData, setAnalyticsData] = useState({
    totalApiCalls: 0,
    todayApiCalls: 0,
    totalPosts: 0,
    publishedPosts: 0,
    totalLikes: 0,
    totalComments: 0,
  });

  // 7일간 API 호출수 차트 데이터
  const [weeklyChartData, setWeeklyChartData] = useState<
    Array<{
      date: string;
      calls: number;
    }>
  >([]);

  // 통합 분석 데이터 로드 함수
  const loadAllAnalyticsData = async () => {
    try {
      // API 호출을 한 번만 수행
      const apiUsageResponse = (await apiClient.get(
        `/api/v1/analytics/api-calls/`,
      )) as any;

      // 특정 인플루언서의 API 호출 데이터 필터링
      const influencerApiCalls = apiUsageResponse.filter(
        (call: any) => call.influencer_id === params.id?.toString(),
      );

      // loadAnalyticsData 로직
      await loadAnalyticsDataWithApiCalls(influencerApiCalls);
      
      // loadWeeklyChartData 로직
      await loadWeeklyChartDataWithApiCalls(influencerApiCalls);
    } catch (error) {
      console.error("분석 데이터 로드 실패:", error);
    }
  };

  // 7일간 API 호출수 데이터 로드 (API 호출 데이터를 받아서 처리)
  const loadWeeklyChartDataWithApiCalls = async (influencerApiCalls: any[]) => {
    try {

      // 최근 7일간 데이터 생성
      const last7Days = [];
      for (let i = 6; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        const dateStr = date.toISOString().split("T")[0];

        // 해당 날짜의 API 호출수 찾기
        const dayCalls = influencerApiCalls
          .filter((call: any) => call.created_at?.startsWith(dateStr))
          .reduce(
            (sum: number, call: any) => sum + (call.daily_call_count || 0),
            0,
          );

        last7Days.push({
          date: dateStr,
          calls: dayCalls,
        });
      }

      setWeeklyChartData(last7Days);
    } catch (error) {
      // console.error("7일간 차트 데이터 로드 실패:", error);
      setWeeklyChartData([]);
    }
  };

  // Instagram 상태 변경 시 처리
  React.useEffect(() => {
    // Instagram 상태 업데이트 처리
  }, [instagramStatus]);


  // 게시글 데이터 로드
  const loadPostsData = async () => {
    setIsPostsLoading(true);
    try {
      // 특정 인플루언서의 게시글만 조회
      const boardData = await apiClient.get<any[]>(
        `/api/v1/boards?influencer_id=${params.id}`,
      );

      // 인플루언서 정보 조회
      const influencerResponse = await apiClient.get(`/api/v1/influencers/${params.id}`);
      const influencerData = influencerResponse as any;

      // 게시글 데이터 변환
      const transformedPosts: ContentPost[] = boardData.map((board: any) => {
        // 인플루언서 ID를 통해 인플루언서 정보 사용
        const influencerName =
          board.influencer_name || influencerData?.influencer_name || "AI 인플루언서";
        const influencerDescription =
          board.influencer_description || influencerData?.influencer_description || "";

        const basePost = {
          id: board.board_id,
          title: board.board_topic || "제목 없음",
          content: board.board_description || "",
          platform: getPlatformName(board.board_platform),
          status: getStatusName(board.board_status),
          publishedAt: board.published_at || board.created_at || "",
          scheduledAt: board.reservation_at || "",
          hashtags: board.board_hash_tag
            ? board.board_hash_tag
              .split(" ")
              .filter((tag: string) => tag.trim())
              .map((tag: string) => (tag.startsWith("#") ? tag : `#${tag}`))
            : [],
          media: {
            type: board.image_url && board.image_url.split(",").length > 1 ? "carousel" as const : "image" as const,
            urls: board.image_url
              ? board.image_url.split(",").map((url: string) => url.trim()).filter(Boolean)
              : ["/placeholder.svg?height=400&width=400"],
            thumbnailUrl: board.image_url ? board.image_url.split(",")[0]?.trim() || "/placeholder.svg?height=400&width=400" : "/placeholder.svg?height=400&width=400",
          },
          // 인플루언서 정보: 조회한 값 사용
          influencerId: board.influencer_id,
          influencerName: influencerName,
          influencerDescription: influencerDescription,
          // Instagram 링크 추가
          instagram_link: board.instagram_link || undefined,
        };

        // 인스타그램 통계 정보 추가
        const instagramStats = board.instagram_stats || {
          like_count: 0,
          comments_count: 0,
        };

        return {
          ...basePost,
          engagement: {
            likes: instagramStats.like_count || 0,
            comments: instagramStats.comments_count || 0,
          },
        };
      });

      setPosts(transformedPosts);
    } catch (error) {
      // 에러 시 빈 배열로 설정
      setPosts([]);
    } finally {
      setIsPostsLoading(false);
    }
  };

  // 플랫폼 번호를 이름으로 변환
  const getPlatformName = (platformNumber: number) => {
    switch (platformNumber) {
      case 0:
        return "Instagram";
      case 1:
        return "Blog";
      case 2:
        return "Facebook";
      case 3:
        return "Twitter";
      case 4:
        return "TikTok";
      case 5:
        return "YouTube";
      default:
        return "Instagram";
    }
  };

  // 상태 번호를 이름으로 변환
  const getStatusName = (statusNumber: number) => {
    switch (statusNumber) {
      case 1:
        return "draft" as const; // 임시저장
      case 2:
        return "scheduled" as const; // 예약됨
      case 3:
        return "published" as const; // 발행됨
      default:
        return "draft" as const;
    }
  };

  // 분석 데이터 로드 (API 호출 데이터를 받아서 처리)
  const loadAnalyticsDataWithApiCalls = async (influencerApiCalls: any[]) => {
    try {
      // 게시글 데이터가 로드된 후 분석 데이터 계산
      const publishedPosts = posts.filter((p) => p.status === "published");

      // API 사용량 데이터 가져오기
      let apiUsageData = {
        totalApiCalls: 0,
        todayApiCalls: 0,
      };

      try {
        // 총 API 호출 수와 오늘 호출 수 계산
        const totalCalls = influencerApiCalls.reduce(
          (sum: number, call: any) => sum + (call.daily_call_count || 0),
          0,
        );

        // 오늘 날짜의 호출 수 계산
        const today = new Date().toISOString().split("T")[0];
        const todayCalls = influencerApiCalls
          .filter((call: any) => call.created_at?.startsWith(today))
          .reduce(
            (sum: number, call: any) => sum + (call.daily_call_count || 0),
            0,
          );

        apiUsageData = {
          totalApiCalls: totalCalls,
          todayApiCalls: todayCalls,
        };
      } catch (error) {
        // 오류 발생 시 기본값 사용
        apiUsageData = {
          totalApiCalls: 0,
          todayApiCalls: 0,
        };
      }

      setAnalyticsData({
        ...apiUsageData,
        totalPosts: posts.length,
        publishedPosts: publishedPosts.length,
        totalLikes: publishedPosts.reduce(
          (sum, p) => sum + (p.engagement?.likes || 0),
          0,
        ),
        totalComments: publishedPosts.reduce(
          (sum, p) => sum + (p.engagement?.comments || 0),
          0,
        ),
      });
    } catch (error) {
      // 기본값 설정
      setAnalyticsData({
        totalApiCalls: 0,
        todayApiCalls: 0,
        totalPosts: 0,
        publishedPosts: 0,
        totalLikes: 0,
        totalComments: 0,
      });
    }
  };

  // 원래 함수들 (독립적으로 호출될 때를 위해 유지)
  const loadWeeklyChartData = async () => {
    try {
      const apiUsageResponse = (await apiClient.get(
        `/api/v1/analytics/api-calls/`,
      )) as any;

      const influencerApiCalls = apiUsageResponse.filter(
        (call: any) => call.influencer_id === params.id?.toString(),
      );

      await loadWeeklyChartDataWithApiCalls(influencerApiCalls);
    } catch (error) {
      console.error("주간 차트 데이터 로드 실패:", error);
    }
  };

  const loadAnalyticsData = async () => {
    try {
      const apiUsageResponse = (await apiClient.get(
        `/api/v1/analytics/api-calls/`,
      )) as any;

      const influencerApiCalls = apiUsageResponse.filter(
        (call: any) => call.influencer_id === params.id?.toString(),
      );

      await loadAnalyticsDataWithApiCalls(influencerApiCalls);
    } catch (error) {
      console.error("분석 데이터 로드 실패:", error);
    }
  };

  // posts 데이터 로드 추적
  const analyticsLoadedRef = useRef(false);
  
  // 게시글 데이터가 로드된 후 분석 데이터 업데이트 (중복 호출 방지)
  React.useEffect(() => {
    if (!analyticsLoadedRef.current && posts.length >= 0) {
      analyticsLoadedRef.current = true;
      // 빈 배열도 포함하여 초기 로드 시에도 실행
      loadAllAnalyticsData(); // 통합 함수 호출
    }
  }, [posts.length]); // posts 배열 전체가 아닌 길이만 감지하여 불필요한 재호출 방지

  // 모델 데이터 로드
  const loadModelData = async () => {
    setIsModelLoading(true);
    try {
      const data = await ModelService.getInfluencer(params.id as string);

      // 이미지 URL 처리: S3 키인 경우 URL로 변환
      let processedImageUrl = data.image_url;
      // presigned URL이므로 추가 가공 없이 그대로 사용
      setModel({
        ...data,
        id: data.influencer_id,
        name: data.influencer_name,
        description: data.influencer_description || "",
        image_url: processedImageUrl, // 그대로 사용
        system_prompt: data.system_prompt || "",
        createdAt: data.created_at?.split("T")[0] || "",
        apiKey: sampleModel.apiKey, // API 키는 별도 조회
        trainingData: sampleModel.trainingData, // 훈련 데이터는 별도 조회
        // Instagram 연동 정보 추가
        instagram_id: data.instagram_id,
        instagram_username: data.instagram_username,
        instagram_account_type: data.instagram_account_type,
        instagram_is_active: data.instagram_is_active,
        instagram_connected_at: data.instagram_connected_at,
      });

      // API 키 정보 로드
      await loadApiKeyInfo();
    } catch (error) {
      // 에러 처리
      // console.error("❌ 모델 데이터 로드 실패:", error);
    } finally {
      setIsModelLoading(false);
    }
  };

  // API 키 정보 로드
  const loadApiKeyInfo = async () => {
    // 현재 로그인한 사용자 정보 확인
    const token = localStorage.getItem("access_token");
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split(".")[1]));
      } catch (e) { }
    } else {
    }

    try {
      const apiKeyData = await ModelService.getApiKey(params.id as string);

      setApiKeyInfo({
        api_key: apiKeyData.api_key,
        created_at: apiKeyData.created_at,
        updated_at: apiKeyData.updated_at,
      });
      // 모델 상태에 API 키 업데이트
      setModel((prev: any) => ({
        ...prev,
        apiKey: apiKeyData.api_key,
      }));
    } catch (error: any) {
      // console.error("❌ API 키 조회 실패:", {
      //   error: error,
      //   status: error.status,
      //   detail: error.data?.detail,
      //   message: error.message,
      //   influencer_id: params.id,
      //   stack: error.stack,
      // });

      // API 키가 없는 경우 (404)에만 자동 생성 시도
      if (error.status === 404 && error.data?.detail === "API key not found") {
        try {
          const response = await ModelService.generateApiKey(
            params.id as string,
          );

          setApiKeyInfo({
            api_key: response.api_key,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          });
          // 모델 상태에 API 키 업데이트
          setModel((prev: any) => ({
            ...prev,
            apiKey: response.api_key,
          }));
        } catch (generateError: any) {
          setApiKeyInfo(null);
        }
      } else {
        // 다른 오류 (인플루언서를 찾을 수 없음 등)는 그대로 표시
        // console.error(
        //   "API 키 조회 실패:",
        //   error.response?.data?.detail || error.message,
        // );
        setApiKeyInfo(null);
      }
    }
  };

  // 이미지 파일 처리 공통 함수
  const processImageFile = async (file: File) => {
    // 이미지 파일 검증
    if (!file.type.startsWith("image/")) {
      toast({
        title: "파일 형식 오류",
        description: "이미지 파일만 업로드할 수 있습니다.",
        variant: "destructive",
      });
      return;
    }

    // 파일 크기 제한 (5MB)
    if (file.size > 5 * 1024 * 1024) {
      toast({
        title: "파일 크기 오류",
        description: "이미지 파일 크기는 5MB 이하여야 합니다.",
        variant: "destructive",
      });
      return;
    }

    try {
      setUploadedImage(file);

      // 이미지 미리보기 생성
      const reader = new FileReader();
      reader.onload = (e) => {
        setImagePreview(e.target?.result as string);
        setHasImageChanges(true); // 이미지 변경 감지
      };
      reader.readAsDataURL(file);
    } catch (error) {
      toast({
        title: "이미지 처리 오류",
        description: "이미지 처리 중 오류가 발생했습니다.",
        variant: "destructive",
      });
      // console.error("Image processing error:", error);
    }
  };

  // 이미지 업로드 처리
  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await processImageFile(file);
    }
  };

  // 드래그 앤 드롭 이벤트 처리
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);

    const files = e.dataTransfer.files;
    if (files && files[0]) {
      await processImageFile(files[0]);
    }
  };

  // 이미지 제거
  const removeImage = () => {
    setUploadedImage(null);
    setImagePreview(null);
    setHasImageChanges(false); // 이미지 제거 시 변경 상태 초기화
    // 파일 입력 초기화
    const fileInput = document.getElementById(
      "modal-image-upload",
    ) as HTMLInputElement;
    if (fileInput) {
      fileInput.value = "";
    }
  };

  const openImageModal = () => {
    setIsImageModalOpen(true);
  };

  const openGalleryModal = async () => {
    setIsGalleryModalOpen(true);
    await loadGalleryImages(1);
  };

  const loadGalleryImages = async (page: number = 1) => {
    try {
      setIsLoadingGallery(true);

      // 팀 ID 가져오기 (사용자 정보에서)
      const teamId = user?.teams?.[0]?.group_id;
      if (!teamId) {
        toast({
          title: "팀 정보 없음",
          description: '소속된 팀이 없습니다.',
          variant: "destructive",
          duration: 3000,
        });
        return;
      }

      const data = await galleryService.getImages({
        page: page,
        page_size: 12,
        team_id: teamId
      });

      setGalleryImages(data.images);
      setGalleryTotalPages(data.pagination.total_pages);
      setGalleryTotalImages(data.pagination.total_count);
      setGalleryCurrentPage(data.pagination.page);
    } catch (error) {
      toast({
        title: "갤러리 로드 실패",
        description: "이미지 목록을 불러오는데 실패했습니다.",
        variant: "destructive",
        duration: 3000,
      });
    } finally {
      setIsLoadingGallery(false);
    }
  };

  const handleGalleryPageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= galleryTotalPages) {
      setGalleryCurrentPage(newPage);
      loadGalleryImages(newPage);
    }
  };

  const selectGalleryImage = async (imageUrl: string) => {
    try {
      setIsUpdating(true);
      
      // 인플루언서 정보 업데이트 (이미지 URL만 변경)
      const updateData: any = {
        influencer_name: model.name,
        influencer_description: model.description,
        system_prompt: model.system_prompt,
        image_url: imageUrl, // 갤러리에서 선택한 이미지 URL
      };

      const updatedData = await ModelService.updateInfluencer(
        params.id?.toString() ?? "",
        updateData,
      );

      // S3 키라면 전체 URL로 변환
      let fullImageUrl = updatedData.image_url;
      if (fullImageUrl && !fullImageUrl.startsWith("http")) {
        fullImageUrl = `https://aimex-influencers.s3.ap-northeast-2.amazonaws.com/${fullImageUrl}`;
      }
      if (fullImageUrl) {
        fullImageUrl += `?t=${Date.now()}`;
      }

      // 모델 상태 업데이트
      setModel((prev: any) => ({
        ...prev,
        name: updatedData.influencer_name,
        description: updatedData.influencer_description || "",
        image_url: fullImageUrl || prev.image_url,
      }));

      setHasImageChanges(false);
      setIsGalleryModalOpen(false);

      // 모델 데이터 다시 로드하여 변경사항 반영
      await loadModelData();

      // 성공 토스트 표시
      toast({
        title: "이미지 변경 완료",
        description: "갤러리에서 선택한 이미지로 프로필이 변경되었습니다.",
        variant: "default",
      });

      // 현재 페이지로 리다이렉트 (새로고침)
      let influencerId: string | undefined;
      if (typeof params.id === "string") {
        influencerId = params.id;
      } else if (Array.isArray(params.id)) {
        influencerId = params.id[0];
      }
      router.replace(influencerId ? `/model/${influencerId}` : "/dashboard");
    } catch (error) {
      // 실패 토스트 표시
      toast({
        title: "오류",
        description: "이미지 변경에 실패했습니다. 다시 시도해주세요.",
        variant: "destructive",
      });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleUpdateModel = async () => {
    setIsUpdating(true);
    try {
      let imageUrl = null;

      // 이미지가 업로드된 경우 S3에 업로드
      if (uploadedImage) {
        setIsUploadingImage(true);
        try {
          const formData = new FormData();
          formData.append("file", uploadedImage);
          formData.append("influencer_id", params.id?.toString() ?? "");

          const backendUrl =
            process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
          const response = await fetch(
            `${backendUrl}/api/v1/influencers/upload-image`,
            {
              method: "POST",
              headers: {
                Authorization: `Bearer ${localStorage.getItem("access_token")}`,
              },
              body: formData,
            },
          );

          if (response.ok) {
            const result = await response.json();
            imageUrl = result.file_url;
          }
        } finally {
          setIsUploadingImage(false);
        }
      }

      // 인플루언서 정보 업데이트
      const updateData: any = {
        influencer_name: model.name,
        influencer_description: model.description,
        system_prompt: model.system_prompt,
      };

      if (imageUrl) {
        updateData.image_url = imageUrl;
      }

      const updatedData = await ModelService.updateInfluencer(
        params.id?.toString() ?? "",
        updateData,
      );

      // S3 키라면 전체 URL로 변환
      let fullImageUrl = updatedData.image_url;
      if (fullImageUrl && !fullImageUrl.startsWith("http")) {
        fullImageUrl = `https://aimex-influencers.s3.ap-northeast-2.amazonaws.com/${fullImageUrl}`;
      }
      if (fullImageUrl) {
        fullImageUrl += `?t=${Date.now()}`;
      }

      setModel((prev: any) => ({
        ...prev,
        name: updatedData.influencer_name,
        description: updatedData.influencer_description || "",
        image_url: fullImageUrl || prev.image_url,
      }));

      // 이미지 업로드 후 상태 초기화
      if (uploadedImage) {
        setUploadedImage(null);
        setImagePreview(null);
      }
      setHasImageChanges(false);

      // 모델 데이터 다시 로드하여 변경사항 반영 (선택적)
      await loadModelData();

      // 성공 토스트 표시
      toast({
        title: "성공",
        description: "모델 정보가 성공적으로 업데이트되었습니다!",
        variant: "default",
      });

      // 페이지 새로고침 없이 UI 업데이트
      // setModel((prev: any) => ({
      //   ...prev,
      //   name: updatedData.influencer_name,
      //   description: updatedData.influencer_description || "",
      //   image_url: updatedData.image_url || prev.image_url,
      // }));

      // 현재 페이지로 리다이렉트 (새로고침)
      let influencerId: string | undefined;
      if (typeof params.id === "string") {
        influencerId = params.id;
      } else if (Array.isArray(params.id)) {
        influencerId = params.id[0];
      }
      router.replace(influencerId ? `/model/${influencerId}` : "/dashboard");
    } catch (error) {
      // 실패 토스트 표시
      toast({
        title: "오류",
        description: "모델 정보 업데이트에 실패했습니다. 다시 시도해주세요.",
        variant: "destructive",
      });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDeleteModel = async () => {
    // 실제로는 API 호출로 모델 삭제
    setTimeout(() => {
      // 삭제 후 대시보드로 리다이렉트
      window.location.href = "/dashboard";
    }, 1000);
  };

  const copyApiKey = async () => {
    if (!model.apiKey) {
      toast({
        title: "API 키 없음",
        description: "복사할 API 키가 없습니다.",
        variant: "destructive",
      });
      return;
    }

    try {
      await navigator.clipboard.writeText(model.apiKey);
      toast({
        title: "API 키 복사 완료",
        description: "API 키가 클립보드에 복사되었습니다!",
        variant: "default",
      });
    } catch (error) {
      // console.error("API key copy error:", error);
      toast({
        title: "복사 실패",
        description: "API 키 복사에 실패했습니다. 수동으로 복사해주세요.",
        variant: "destructive",
      });
    }
  };

  const generateNewApiKey = async () => {
    setIsGeneratingApiKey(true);
    try {
      const response = await ModelService.generateApiKey(params.id as string);
      setApiKeyInfo({
        api_key: response.api_key,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
      // 모델 상태에 API 키 업데이트
      setModel((prev: any) => ({ ...prev, apiKey: response.api_key }));
      toast({
        title: "API 키 생성 완료",
        description: "새로운 API 키가 성공적으로 생성되었습니다!",
        variant: "default",
      });
    } catch (error) {
      // console.error("API key generation error:", error);
      toast({
        title: "API 키 생성 실패",
        description: "API 키 생성에 실패했습니다. 다시 시도해주세요.",
        variant: "destructive",
      });
    } finally {
      setIsGeneratingApiKey(false);
    }
  };

  const testChatbot = async () => {
    if (!testMessage.trim() || !model.apiKey) {
      toast({
        title: "입력 오류",
        description: "메시지를 입력하고 API 키가 있어야 합니다.",
        variant: "destructive",
      });
      return;
    }

    setIsTestingChatbot(true);
    try {
      const response = await ModelService.callChatbot(model.apiKey, {
        message: testMessage,
      });
      setTestResponse(response.response);
    } catch (error: any) {
      // console.error("Chatbot test error:", error);
      setTestResponse(
        `오류: ${error.response?.data?.detail || error.message || "알 수 없는 오류"}`,
      );
    } finally {
      setIsTestingChatbot(false);
    }
  };

  const handleChatbotToggle = async () => {
    try {
      // 챗봇 옵션 토글 (true -> false, false -> true)
      const newChatbotOption = !model.chatbot_option;
      // 백엔드 API 호출하여 chatbot_option 업데이트
      await ModelService.updateInfluencer(params.id as string, {
        chatbot_option: newChatbotOption,
      });
      // 로컬 상태 업데이트
      setModel((prev: any) => ({
        ...prev,
        chatbot_option: newChatbotOption,
      }));
      if (newChatbotOption) {
        toast({
          title: "챗봇 활성화",
          description: "챗봇이 활성화되었습니다!",
          variant: "default",
        });
      } else {
        toast({
          title: "챗봇 비활성화",
          description: "챗봇이 비활성화되었습니다.",
          variant: "default",
        });
      }
    } catch (error: any) {
      // console.error("Chatbot toggle error:", error);
      toast({
        title: "오류",
        description: "챗봇 상태 변경에 실패했습니다.",
        variant: "destructive",
      });
    }
  };

  // Instagram 연동 관련 함수들
  const handleInstagramConnect = async () => {
    setIsConnecting(true);

    try {
      // Instagram API with Instagram Login OAuth URL 생성
      const instagramAppId = process.env.NEXT_PUBLIC_INSTAGRAM_APP_ID;
      const redirectUri = `${window.location.origin}/auth/instagram/callback`;
      // Instagram API with Instagram Login 스코프 설정
      const scope =
        "instagram_business_basic,instagram_business_manage_messages,instagram_business_manage_comments,instagram_business_content_publish";

      const authUrl =
        `https://api.instagram.com/oauth/authorize` +
        `?client_id=${instagramAppId}` +
        `&redirect_uri=${encodeURIComponent(redirectUri)}` +
        `&scope=${scope}` +
        `&response_type=code` +
        `&state=${params.id}`; // 모델 ID를 state로 전달

      // 팝업 창으로 Instagram OAuth 페이지 열기
      const popup = window.open(
        authUrl,
        "instagram-auth",
        "width=600,height=700,scrollbars=yes,resizable=yes",
      );

      // 팝업에서 메시지를 기다림
      const handleMessage = async (event: MessageEvent) => {
        if (event.origin !== window.location.origin) return;

        const { type, code, error, state } = event.data;

        if (type === "INSTAGRAM_AUTH_SUCCESS" && code && state === params.id) {
          popup?.close();
          window.removeEventListener("message", handleMessage);

          try {
            // 백엔드에 code 전송하여 토큰 교환 및 계정 연동
            const data = await ModelService.connectInstagram(
              params.id as string,
              {
                code: code,
                redirect_uri: redirectUri,
              },
            );

            setInstagramStatus({
              is_connected: true,
              connected_at: new Date().toISOString(),
              token_expired: false,
              instagram_info: data.instagram_info || {
                id: "",
                username: "",
                account_type: "",
              },
            });
            toast({
              title: "Instagram 연동 완료",
              description:
                "Instagram 비즈니스 계정이 성공적으로 연동되었습니다!",
              variant: "default",
            });
          } catch (error: any) {
            toast({
              title: "Instagram 연동 실패",
              description: "Instagram 연동에 실패했습니다. 다시 시도해주세요.",
              variant: "destructive",
            });
          }

          setIsConnecting(false);
        } else if (type === "INSTAGRAM_AUTH_ERROR" || error) {
          popup?.close();
          window.removeEventListener("message", handleMessage);
          setIsConnecting(false);
          toast({
            title: "Instagram 연동 취소",
            description: "Instagram 연동이 취소되었거나 오류가 발생했습니다.",
            variant: "destructive",
          });
        }
      };

      window.addEventListener("message", handleMessage);

      // 팝업이 닫힌 경우 처리
      const checkClosed = setInterval(() => {
        if (popup?.closed) {
          clearInterval(checkClosed);
          window.removeEventListener("message", handleMessage);
          setIsConnecting(false);
        }
      }, 1000);
    } catch (error) {
      setIsConnecting(false);
      toast({
        title: "Instagram 연동 오류",
        description: "Instagram 연동 중 오류가 발생했습니다.",
        variant: "destructive",
      });
    }
  };

  const handleInstagramDisconnect = async () => {
    try {
      // API 호출하여 Instagram 연동 해제
      await ModelService.disconnectInstagram(params.id as string);

      setInstagramStatus({
        is_connected: false,
      });
      toast({
        title: "Instagram 연동 해제",
        description: "Instagram 계정 연동이 해제되었습니다.",
        variant: "default",
      });
    } catch (error) {
      toast({
        title: "Instagram 연동 해제 실패",
        description: "Instagram 연동 해제에 실패했습니다. 다시 시도해주세요.",
        variant: "destructive",
      });
    }
  };

  // 초기 데이터 로드 상태 추적
  const initialLoadRef = useRef(false);
  
  // 컴포넌트 마운트 시 모델 데이터 로드 (한 번만 실행)
  React.useEffect(() => {
    if (!initialLoadRef.current) {
      initialLoadRef.current = true;
      const loadData = async () => {
        await loadModelData();
        await loadPostsData();
      };
      loadData();
    }
  }, []); // 의존성 배열을 비워서 마운트 시 한 번만 실행

  // 모델 데이터 로드 후 Instagram 상태 확인
  // 컴포넌트 언마운트 시 오디오 정리
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  // 모델 관련 추가 데이터 로드 추적
  const modelExtraDataLoadedRef = useRef(false);
  
  React.useEffect(() => {
    if (!isModelLoading && model && !modelExtraDataLoadedRef.current) {
      modelExtraDataLoadedRef.current = true;
      // 베이스 음성 확인
      checkBaseVoice();
      const checkInstagramStatus = async () => {
        try {
          // Instagram이 연동되어 있으면 API로 실시간 정보 조회
          if (model.instagram_is_active) {
            try {
              const data = await ModelService.getInstagramStatus(
                params.id as string,
              );
              setInstagramStatus({
                is_connected: data.is_connected,
                instagram_id: data.instagram_id,
                instagram_page_id: data.instagram_page_id,
                instagram_username: data.instagram_username,
                instagram_account_type: data.instagram_account_type,
                connected_at: data.connected_at,
                token_expires_at: data.token_expires_at,
                token_expired: data.token_expired,
                instagram_info: data.instagram_info,
              });
            } catch (error) {
              // API 호출 실패 시 기본 정보 사용
              setInstagramStatus({
                is_connected: true,
                connected_at: model.instagram_connected_at,
                instagram_info: {
                  id: model.instagram_id || "",
                  username: model.instagram_username || "",
                  account_type: model.instagram_account_type || "",
                },
              });
            }
          } else {
            // Instagram이 연동되지 않은 경우
            setInstagramStatus({ is_connected: false });
          }
        } catch (error) {
          setInstagramStatus({ is_connected: false });
        }
      };

      checkInstagramStatus();
    }
  }, [isModelLoading, model, params.id]);

  // 예약된 게시글이 있을 때 주기적으로 상태 확인 (30초마다)
  // 음성 탭을 로드한 적이 있는지 추적
  const voiceTabLoadedRef = useRef(false);
  
  // 음성 탭이 선택되었을 때 음성 히스토리 로드 (탭당 한 번만)
  React.useEffect(() => {
    if (activeTab === "voice" && !voiceTabLoadedRef.current && !isLoadingVoiceHistory) {
      voiceTabLoadedRef.current = true;
      loadVoiceHistory();
    }
    
    // 탭이 변경될 때 ref 리셋
    if (activeTab !== "voice") {
      voiceTabLoadedRef.current = false;
    }
  }, [activeTab, isLoadingVoiceHistory]); // activeTab과 isLoadingVoiceHistory만 의존성으로 사용

  // pending 상태의 음성이 있을 때 주기적으로 상태 확인 (3초마다)
  React.useEffect(() => {
    // 현재 상태를 ref에 저장
    voiceHistory.forEach((voice) => {
      if (voice.id && voice.status) {
        previousVoiceStatusRef.current.set(voice.id, voice.status);
      }
    });

    const hasPendingVoices = voiceHistory.some(
      (voice) => voice.status === "pending",
    );

    if (hasPendingVoices && activeTab === "voice") {
      const interval = setInterval(async () => {
        // 음성 목록 다시 로드
        const response = await apiClient.get<any[]>(
          `/api/v1/influencers/${params.id}/voices`,
        );
        if (Array.isArray(response)) {
          const updatedVoices = response.map((voice: any) => ({
            id: voice.id,
            text: voice.text,
            url: voice.url || voice.s3_url,
            duration: voice.duration,
            createdAt: voice.createdAt || voice.created_at,
            status: voice.status || "completed",
            task_id: voice.task_id,
          }));

          // 새로 완료된 음성 찾기
          const newlyCompletedVoices = updatedVoices.filter((voice) => {
            const previousStatus = previousVoiceStatusRef.current.get(voice.id);
            return previousStatus === "pending" && voice.status === "completed";
          });

          // 새로 실패한 음성 찾기
          const newlyFailedVoices = updatedVoices.filter((voice) => {
            const previousStatus = previousVoiceStatusRef.current.get(voice.id);
            return previousStatus === "pending" && voice.status === "failed";
          });

          // 상태 업데이트
          setVoiceHistory(updatedVoices);

          // 알림 표시
          if (newlyCompletedVoices.length > 0) {
            toast({
              title: "음성 생성 완료",
              description: `${newlyCompletedVoices.length}개의 음성이 성공적으로 생성되었습니다.`,
            });

            // 첫 번째 완료된 음성 자동 재생 (선택사항)
            if (newlyCompletedVoices[0]?.url) {
              handlePlayVoice(newlyCompletedVoices[0].url);
            }
          }

          if (newlyFailedVoices.length > 0) {
            toast({
              title: "음성 생성 실패",
              description: `${newlyFailedVoices.length}개의 음성 생성에 실패했습니다.`,
              variant: "destructive",
            });
          }
        }
      }, 3000); // 3초마다 확인

      return () => clearInterval(interval);
    }
  }, [voiceHistory, activeTab, params.id]);

  // SSE 연결을 통한 음성 상태 실시간 모니터링 (기존 폴링 보완)
  React.useEffect(() => {
    let eventSource: EventSource | null = null;

    // pending 상태의 음성이 있고 voice 탭이 활성화되어 있을 때만 SSE 연결
    const hasPendingVoices = voiceHistory.some(voice => voice.status === "pending");

    if (hasPendingVoices && activeTab === "voice") {
      const token = tokenUtils.getToken();
      if (!token) return;

      try {
        // SSE 연결 생성 (토큰을 URL 파라미터로 전달)
        eventSource = new EventSource(
          `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/api/v1/influencers/${params.id}/voices/status-stream?token=${token}`
        );

        // 연결 성공
        eventSource.onopen = () => {
          console.log("✅ SSE 연결 성공: 음성 상태 모니터링 시작");
        };

        // 메시지 수신
        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            switch (data.event) {
              case "voice_status_update":
                // 음성 상태 업데이트
                if (data.data && Array.isArray(data.data)) {
                  setVoiceHistory(prev => {
                    const updatedHistory = [...prev];

                    // 새로 완료된/실패한 음성 찾기 (알림용)
                    const newlyCompletedVoices: any[] = [];
                    const newlyFailedVoices: any[] = [];

                    data.data.forEach((updatedVoice: any) => {
                      const index = updatedHistory.findIndex(v => v.id === updatedVoice.id);
                      if (index !== -1) {
                        const previousStatus = updatedHistory[index].status;
                        const newStatus = updatedVoice.status;

                        // 상태 변화 감지
                        if (previousStatus === "pending" && newStatus === "completed") {
                          newlyCompletedVoices.push(updatedVoice);
                        } else if (previousStatus === "pending" && newStatus === "failed") {
                          newlyFailedVoices.push(updatedVoice);
                        }

                        updatedHistory[index] = {
                          ...updatedHistory[index],
                          ...updatedVoice,
                          createdAt: updatedVoice.created_at || updatedVoice.createdAt
                        };
                      }
                    });

                    // 기존 폴링 알림은 SSE가 활성화되면 비활성화
                    // 알림 표시는 SSE에서만 처리
                    if (newlyCompletedVoices.length > 0) {
                      toast({
                        title: "음성 생성 완료 (실시간)",
                        description: `${newlyCompletedVoices.length}개의 음성이 성공적으로 생성되었습니다.`,
                      });

                      // 첫 번째 완료된 음성 자동 재생 (선택사항)
                      if (newlyCompletedVoices[0]?.url) {
                        handlePlayVoice(newlyCompletedVoices[0].url);
                      }
                    }
                    if (newlyFailedVoices.length > 0) {
                      toast({
                        title: "음성 생성 실패 (실시간)",
                        description: `${newlyFailedVoices.length}개의 음성 생성에 실패했습니다.`,
                        variant: "destructive",
                      });
                    }

                    return updatedHistory;
                  });

                  console.log("🔄 SSE: 음성 상태 업데이트", data.data);
                }
                break;

              case "all_completed":
                // 모든 음성 생성 완료
                console.log("✅ SSE: 모든 음성 생성 완료");
                if (eventSource) {
                  eventSource.close();
                  eventSource = null;
                }
                break;

              case "error":
                // 오류 발생
                console.error("❌ SSE 오류:", data.data?.message);
                if (eventSource) {
                  eventSource.close();
                  eventSource = null;
                }
                break;
            }
          } catch (error) {
            console.error("SSE 메시지 파싱 오류:", error);
          }
        };

        // 연결 오류
        eventSource.onerror = (error) => {
          console.error("❌ SSE 연결 오류:", error);
          if (eventSource) {
            eventSource.close();
            eventSource = null;
          }
        };

      } catch (error) {
        console.error("SSE 연결 생성 실패:", error);
      }
    }

    // 컴포넌트 언마운트 또는 탭 변경 시 SSE 연결 해제
    return () => {
      if (eventSource) {
        console.log("🔌 SSE 연결 해제");
        eventSource.close();
        eventSource = null;
      }
    };
  }, [voiceHistory.filter(v => v.status === "pending").length, activeTab, params.id]);

  React.useEffect(() => {
    const hasScheduledPosts = posts.some((post) => post.status === "scheduled");

    if (hasScheduledPosts) {
      const interval = setInterval(async () => {
        await loadPostsData(); // 예약된 게시글이 있으면 30초마다 새로고침

        // 상태 변경 감지
        const updatedPosts = await apiClient.get<any[]>(
          `/api/v1/boards?influencer_id=${params.id}`,
        );
        const transformedPosts: ContentPost[] = updatedPosts.map(
          (board: any) => {
            const influencerName =
              board.influencer_name || model?.name || "AI 인플루언서";
            const influencerDescription =
              board.influencer_description || model?.description || "";

            const basePost = {
              id: board.board_id,
              title: board.board_topic || "제목 없음",
              content: board.board_description || "",
              platform: getPlatformName(board.board_platform),
              status: getStatusName(board.board_status),
              publishedAt: board.published_at || board.created_at || "",
              scheduledAt: board.reservation_at || "",
              hashtags: board.board_hash_tag
                ? board.board_hash_tag
                  .split(" ")
                  .filter((tag: string) => tag.trim())
                  .map((tag: string) =>
                    tag.startsWith("#") ? tag : `#${tag}`,
                  )
                : [],
              media: {
                type: "image" as const,
                urls: [
                  board.image_url || "/placeholder.svg?height=400&width=400",
                ],
                thumbnailUrl:
                  board.image_url || "/placeholder.svg?height=400&width=400",
              },
              influencerId: board.influencer_id,
              influencerName: influencerName,
              influencerDescription: influencerDescription,
              instagram_link: board.instagram_link || undefined,
            };

            const instagramStats = board.instagram_stats || {
              like_count: 0,
              comments_count: 0,
            };

            return {
              ...basePost,
              engagement: {
                likes: instagramStats.like_count || 0,
                comments: instagramStats.comments_count || 0,
              },
            };
          },
        );

        // 상태 변경 감지 및 로그
        const currentPostIds = new Set(posts.map((p) => p.id));
        const updatedPostIds = new Set(transformedPosts.map((p) => p.id));

        // 새로 발행된 게시글 감지
        const newlyPublished = transformedPosts.filter(
          (post) =>
            post.status === "published" &&
            posts.find((p) => p.id === post.id)?.status === "scheduled",
        );

        if (newlyPublished.length > 0) {
          setPosts(transformedPosts);
          await loadAnalyticsData(); // 분석 데이터도 갱신

          // 사용자에게 알림 (선택사항)
          if (newlyPublished.length === 1) {
          } else {
          }
        }
      }, 30000); // 30초로 단축

      return () => clearInterval(interval);
    }
  }, [posts, params.id, model]);

  const getStatusBadge = (status: ContentPost["status"]) => {
    switch (status) {
      case "published":
        return (
          <Badge className="bg-green-100 text-green-800 whitespace-nowrap">
            발행됨
          </Badge>
        );
      case "scheduled":
        return (
          <Badge className="bg-blue-100 text-blue-800 whitespace-nowrap">
            예약됨
          </Badge>
        );
      case "draft":
        return (
          <Badge className="bg-gray-100 text-gray-800 whitespace-nowrap">
            임시저장
          </Badge>
        );
      default:
        return (
          <Badge variant="secondary" className="whitespace-nowrap">
            알 수 없음
          </Badge>
        );
    }
  };

  const getPlatformBadge = (platform: string) => {
    const colors: Record<string, string> = {
      Instagram: "bg-pink-100 text-pink-800",
      Facebook: "bg-blue-100 text-blue-800",
      Twitter: "bg-sky-100 text-sky-800",
      TikTok: "bg-purple-100 text-purple-800",
      YouTube: "bg-red-100 text-red-800",
      Blog: "bg-orange-100 text-orange-800",
    };

    return (
      <Badge
        className={`${colors[platform] || "bg-gray-100 text-gray-800"} whitespace-nowrap`}
      >
        {platform}
      </Badge>
    );
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return "";
    return new Date(dateString).toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatFullDate = (dateString: string) => {
    if (!dateString) return "";
    const date = new Date(dateString);
    // 유효한 날짜인지 확인
    if (isNaN(date.getTime())) return "";

    // 한국 시간으로 변환 (UTC + 9시간)
    const koreanTime = new Date(date.getTime() + 9 * 60 * 60 * 1000);

    return koreanTime.toLocaleString("ko-KR", {
      year: "numeric",
      month: "long",
      day: "numeric",
      weekday: "long",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // 게시글 상세 보기 핸들러
  const handleViewPostDetail = (post: ContentPost) => {
    setSelectedPost(post);
    setIsPostDetailModalOpen(true);
    setIsEditing(false);
    setEditTitle(post.title || "");
    setEditContent(post.content || "");
    setEditHashtags((post.hashtags || []).join(" "));
    setEditScheduledAt(post.scheduledAt || "");
  };

  // 게시글 상세 모달 닫기
  const handleClosePostDetail = () => {
    setSelectedPost(null);
    setIsPostDetailModalOpen(false);
  };

  // 게시글 수정 저장
  const handleEditSave = async () => {
    if (!selectedPost || isSaving) return;

    const originalTitle = selectedPost.title || "게시글";
    const hasChanges =
      editTitle !== originalTitle ||
      editContent !== (selectedPost.content || "") ||
      editHashtags !== (selectedPost.hashtags?.join(" ") || "") ||
      editScheduledAt !==
      (selectedPost.scheduledAt ? selectedPost.scheduledAt.slice(0, 16) : "");

    if (!hasChanges) {
      setIsEditing(false);
      return;
    }

    setIsSaving(true);
    try {
      // 백엔드 API 호출하여 게시글 수정
      const boardId = selectedPost.id;
      const updateData = {
        board_topic: editTitle,
        board_description: editContent,
        board_hash_tag: editHashtags,
        ...(editScheduledAt && { reservation_at: `${editScheduledAt}:00` }),
      };

      await apiClient.put(`/api/v1/boards/${boardId}`, updateData);

      // 성공 시 프론트엔드 상태 업데이트
      setPosts((posts) => {
        const newPosts = posts.map((post) => {
          if (post.id !== selectedPost.id) return post;

          return {
            ...post,
            title: editTitle,
            content: editContent,
            hashtags: editHashtags
              .split(" ")
              .filter((tag) => tag.startsWith("#")),
            status: post.status,
            scheduledAt: post.scheduledAt,
          };
        });
        // 최신 selectedPost로 갱신
        const updated = newPosts.find((p) => p.id === selectedPost.id);
        if (updated) setSelectedPost(updated);
        return newPosts;
      });

      // 분석 데이터도 갱신
      await loadAnalyticsData();

      setIsEditing(false);
      setIsPostDetailModalOpen(false);
    } catch (error) {
    } finally {
      setIsSaving(false);
    }
  };

  // 플랫폼별 게시글 렌더링
  const renderPlatformSpecificPost = (post: ContentPost) => {
    switch (post.platform) {
      case "Instagram":
        return (
          <div className="bg-white border rounded-lg overflow-hidden max-w-md mx-auto">
            {/* Instagram 헤더 */}
            <div className="flex items-center justify-between p-3 border-b">
              <div className="flex items-center space-x-3">
                <Avatar className="h-8 w-8">
                  <AvatarFallback className="bg-pink-500 text-white text-xs">
                    AI
                  </AvatarFallback>
                </Avatar>
                <div>
                  <p className="font-semibold text-sm">{model.name}</p>
                  <p className="text-xs text-gray-500">패션 인플루언서</p>
                </div>
              </div>
              <MoreHorizontal className="h-5 w-5 text-gray-600" />
            </div>

            {/* Instagram 이미지/캐러셀 */}
            {post.media && (
              <div className="relative">
                {post.media.type === "carousel" ? (
                  <div className="flex overflow-x-auto snap-x snap-mandatory">
                    {post.media.urls.map((url, index) => (
                      <PostImage
                        key={index}
                        url={url || "/placeholder.svg"}
                        alt={`Slide ${index + 1}`}
                        className="w-full h-80 object-cover flex-shrink-0 snap-start"
                      />
                    ))}
                  </div>
                ) : (
                  <PostImage
                    url={post.media.urls[0] || "/placeholder.svg"}
                    alt="Post image"
                    className="w-full h-80 object-cover"
                  />
                )}
                {post.media.type === "carousel" && (
                  <div className="absolute top-2 right-2 bg-black bg-opacity-50 text-white text-xs px-2 py-1 rounded">
                    1/{post.media.urls.length}
                  </div>
                )}
              </div>
            )}

            {/* Instagram 액션 버튼 */}
            <div className="p-3">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-4">
                  <Heart className="h-6 w-6" />
                  <MessageCircle className="h-6 w-6" />
                </div>
                <Bookmark className="h-6 w-6" />
              </div>

              {/* 좋아요 수 */}
              <p className="font-semibold text-sm mb-2">
                좋아요 {(post.engagement?.likes || 0).toLocaleString()}개
              </p>

              {/* 캡션 */}
              <div className="text-sm">
                <span className="font-semibold">{model.name}</span>{" "}
                <span className="whitespace-pre-wrap">{post.content}</span>
              </div>

              {/* 해시태그 */}
              <div className="mt-2">
                {post.hashtags?.map((tag, index) => (
                  <span key={index} className="text-blue-600 text-sm mr-1">
                    {tag}
                  </span>
                ))}
              </div>

              {/* 댓글 보기 */}
              <p className="text-gray-500 text-sm mt-2">
                댓글 {post.engagement?.comments || 0}개 모두 보기
              </p>
              <p className="text-gray-400 text-xs mt-1">
                {formatDate(post.publishedAt || "")}
              </p>
            </div>
          </div>
        );

      case "Facebook":
        return (
          <div className="bg-white border rounded-lg p-4 max-w-lg mx-auto">
            {/* Facebook 헤더 */}
            <div className="flex items-center space-x-3 mb-3">
              <Avatar className="h-10 w-10">
                <AvatarFallback className="bg-blue-600 text-white">
                  AI
                </AvatarFallback>
              </Avatar>
              <div className="flex-1">
                <p className="font-semibold text-sm">{model.name}</p>
                <p className="text-xs text-gray-500">
                  {formatDate(post.publishedAt || "")} · 🌍
                </p>
              </div>
            </div>

            {/* Facebook 텍스트 */}
            <div className="mb-3">
              <p className="text-sm whitespace-pre-wrap">{post.content}</p>
            </div>

            {/* Facebook 이미지 */}
            {post.media && (
              <div className="mb-3">
                <PostImage
                  url={post.media.urls[0] || "/placeholder.svg"}
                  alt="Post image"
                  className="w-full rounded-lg"
                />
              </div>
            )}

            {/* Facebook 반응 */}
            <div className="border-t pt-2">
              <div className="flex items-center justify-between text-gray-500 text-sm mb-2">
                <span>👍❤️😊 {post.engagement?.likes || 0}</span>
                <span>댓글 {post.engagement?.comments || 0}개</span>
              </div>
              <div className="flex items-center justify-around border-t pt-2">
                <button className="flex items-center space-x-1 text-gray-600 hover:bg-gray-100 px-4 py-2 rounded">
                  <Heart className="h-4 w-4" />
                  <span className="text-sm">좋아요</span>
                </button>
                <button className="flex items-center space-x-1 text-gray-600 hover:bg-gray-100 px-4 py-2 rounded">
                  <MessageCircle className="h-4 w-4" />
                  <span className="text-sm">댓글</span>
                </button>
              </div>
            </div>
          </div>
        );

      case "Twitter":
        return (
          <div className="bg-white border rounded-lg p-4 max-w-md mx-auto">
            {/* Twitter 헤더 */}
            <div className="flex items-start space-x-3">
              <Avatar className="h-10 w-10">
                <AvatarFallback className="bg-sky-500 text-white">
                  AI
                </AvatarFallback>
              </Avatar>
              <div className="flex-1">
                <div className="flex items-center space-x-1">
                  <p className="font-bold text-sm">{model.name}</p>
                  <span className="text-blue-500">✓</span>
                  <p className="text-gray-500 text-sm">
                    @{model.name.replace(/\s+/g, "").toLowerCase()}
                  </p>
                  <span className="text-gray-500">·</span>
                  <p className="text-gray-500 text-sm">
                    {formatDate(post.publishedAt || "")}
                  </p>
                </div>

                {/* Twitter 텍스트 */}
                <div className="mt-2">
                  <p className="text-sm whitespace-pre-wrap">{post.content}</p>
                </div>

                {/* Twitter 이미지 */}
                {post.media && (
                  <div className="mt-3">
                    <PostImage
                      url={post.media.urls[0] || "/placeholder.svg"}
                      alt="Tweet image"
                      className="w-full rounded-2xl border"
                    />
                  </div>
                )}

                {/* Twitter 액션 */}
                <div className="flex items-center justify-between mt-3 max-w-md">
                  <button className="flex items-center space-x-1 text-gray-500 hover:text-blue-500">
                    <MessageCircle className="h-4 w-4" />
                    <span className="text-sm">
                      {post.engagement?.comments || 0}
                    </span>
                  </button>
                  <button className="flex items-center space-x-1 text-gray-500 hover:text-red-500">
                    <Heart className="h-4 w-4" />
                    <span className="text-sm">
                      {post.engagement?.likes || 0}
                    </span>
                  </button>
                  <button className="flex items-center space-x-1 text-gray-500 hover:text-blue-500">
                    <ExternalLink className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        );

      case "TikTok":
        return (
          <div className="bg-black rounded-lg overflow-hidden max-w-xs mx-auto">
            {/* TikTok 비디오 영역 */}
            <div className="relative">
              <div className="aspect-[9/16] bg-gray-900 flex items-center justify-center">
                {post.media?.thumbnailUrl ? (
                  <PostImage
                    url={post.media.thumbnailUrl || "/placeholder.svg"}
                    alt="Video thumbnail"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="text-white text-center">
                    <Play className="h-16 w-16 mx-auto mb-2" />
                    <p className="text-sm">비디오 콘텐츠</p>
                  </div>
                )}
              </div>

              {/* TikTok 사이드 액션 */}
              <div className="absolute right-2 bottom-20 flex flex-col space-y-4">
                <div className="text-center">
                  <div className="w-12 h-12 bg-gray-800 rounded-full flex items-center justify-center mb-1">
                    <Heart className="h-6 w-6 text-white" />
                  </div>
                  <span className="text-white text-xs">
                    {post.engagement?.likes || 0}
                  </span>
                </div>
                <div className="text-center">
                  <div className="w-12 h-12 bg-gray-800 rounded-full flex items-center justify-center mb-1">
                    <MessageCircle className="h-6 w-6 text-white" />
                  </div>
                  <span className="text-white text-xs">
                    {post.engagement?.comments || 0}
                  </span>
                </div>
              </div>

              {/* TikTok 하단 정보 */}
              <div className="absolute bottom-4 left-4 right-16 text-white">
                <p className="font-semibold text-sm mb-1">
                  @{model.name.replace(/\s+/g, "").toLowerCase()}
                </p>
                <p className="text-sm mb-2">{post.content}</p>
                <div className="flex flex-wrap gap-1">
                  {post.hashtags?.slice(0, 3).map((tag, index) => (
                    <span key={index} className="text-xs">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        );

      case "YouTube":
        return (
          <div className="bg-white rounded-lg overflow-hidden max-w-lg mx-auto">
            {/* YouTube 썸네일 */}
            <div className="relative">
              <PostImage
                url={post.media?.thumbnailUrl || "/placeholder.svg"}
                alt="Video thumbnail"
                className="w-full aspect-video object-cover"
              />
              <div className="absolute inset-0 bg-black bg-opacity-20 flex items-center justify-center">
                <div className="w-16 h-16 bg-red-600 rounded-full flex items-center justify-center">
                  <Play className="h-8 w-8 text-white ml-1" />
                </div>
              </div>
              <div className="absolute bottom-2 right-2 bg-black bg-opacity-80 text-white text-xs px-2 py-1 rounded">
                11:23
              </div>
            </div>

            {/* YouTube 정보 */}
            <div className="p-4">
              <h3 className="font-semibold text-sm mb-2 line-clamp-2">
                {post.title}
              </h3>
              <div className="flex items-center space-x-2 mb-2">
                <Avatar className="h-6 w-6">
                  <AvatarFallback className="bg-red-600 text-white text-xs">
                    AI
                  </AvatarFallback>
                </Avatar>
                <p className="text-sm text-gray-600">{model.name}</p>
                <span className="text-red-600 text-xs">✓</span>
              </div>
              <div className="flex items-center space-x-2 text-xs text-gray-500">
                <span>{formatDate(post.publishedAt || "")}</span>
              </div>
              <p className="text-sm text-gray-600 mt-2 line-clamp-2">
                {post.content}
              </p>
            </div>
          </div>
        );

      default:
        return (
          <div className="bg-white border rounded-lg p-4">
            <p className="text-sm whitespace-pre-wrap">{post.content}</p>
          </div>
        );
    }
  };

  // 플랫폼별 성과 계산 함수 추가
  const calculatePlatformStats = () => {
    // Instagram만 남기고 나머지는 제거
    const allPlatforms = ["Instagram"];
    const platformStats: Record<
      string,
      {
        name: string;
        posts: number;
        totalLikes: number;
        totalComments: number;
        avgEngagement: number;
        color: string;
      }
    > = {};

    // Instagram만 0으로 초기화
    allPlatforms.forEach((platform) => {
      platformStats[platform] = {
        name: platform,
        posts: 0,
        totalLikes: 0,
        totalComments: 0,
        avgEngagement: 0,
        color: "",
      };
    });

    posts.forEach((post) => {
      if (post.status === "published" && post.platform === "Instagram") {
        const stats = platformStats[post.platform];
        stats.posts += 1;
        stats.totalLikes += post.engagement?.likes || 0;
        stats.totalComments += post.engagement?.comments || 0;
      }
    });

    // 평균 참여율 계산 및 색상 설정
    Object.keys(platformStats).forEach((platform) => {
      const stats = platformStats[platform];
      const totalEngagement = stats.totalLikes + stats.totalComments;
      stats.avgEngagement =
        stats.posts > 0 ? Math.round(totalEngagement / stats.posts) : 0;

      // Instagram 색상 설정
      stats.color = "bg-pink-500";
    });

    return platformStats;
  };

  const platformStats = calculatePlatformStats();

  // 음성 관련 함수들
  const handleBaseVoiceFileSelect = (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // 파일 크기 체크 (10MB)
    if (file.size > 10 * 1024 * 1024) {
      toast({
        title: "파일 크기 초과",
        description: "음성 파일은 10MB 이하여야 합니다.",
        variant: "destructive",
      });
      return;
    }

    // 오디오 파일 타입 체크
    if (!file.type.startsWith("audio/")) {
      toast({
        title: "파일 형식 오류",
        description: "오디오 파일만 업로드할 수 있습니다.",
        variant: "destructive",
      });
      return;
    }

    setBaseVoiceFile(file);
  };

  const handleUploadBaseVoice = async () => {
    if (!baseVoiceFile) return;

    setIsUploadingBaseVoice(true);
    try {
      // 파일을 Base64로 변환
      const reader = new FileReader();
      const fileData = await new Promise<string>((resolve, reject) => {
        reader.onload = () => {
          const base64 = reader.result as string;
          // data:audio/mp3;base64, 부분을 제거하고 base64 데이터만 추출
          const base64Data = base64.split(",")[1];
          resolve(base64Data);
        };
        reader.onerror = reject;
        reader.readAsDataURL(baseVoiceFile);
      });

      // JSON으로 전송
      const requestData = {
        file_data: fileData,
        file_name: baseVoiceFile.name,
        file_type: baseVoiceFile.type,
      };

      // 베이스 음성 업로드 API 호출
      const response = await apiClient.post<{
        s3_url: string;
        file_name: string;
        file_size: number;
        message: string;
        original_filename?: string;
      }>(`/api/v1/influencers/${params.id}/voice/base`, requestData);

      if (response?.s3_url) {
        setBaseVoiceUrl(response.s3_url);
        setHasBaseVoice(true);
        setBaseVoiceFile(null);

        // 원본 파일명이 있으면 WAV로 변환되었음을 알림
        const description = response.original_filename
          ? `베이스 음성이 WAV 형식으로 변환되어 업로드되었습니다. (원본: ${response.original_filename})`
          : "베이스 음성이 성공적으로 업로드되었습니다.";

        toast({
          title: "업로드 완료",
          description,
        });
      } else {
        throw new Error("응답에 s3_url이 없습니다");
      }
    } catch (error: any) {
      // console.error("베이스 음성 업로드 실패:", error);
      toast({
        title: "업로드 실패",
        description:
          error.response?.data?.detail ||
          "베이스 음성 업로드 중 오류가 발생했습니다.",
        variant: "destructive",
      });
    } finally {
      setIsUploadingBaseVoice(false);
    }
  };

  const handleChangeBaseVoice = () => {
    setHasBaseVoice(false);
    setBaseVoiceUrl(null);
    setBaseVoiceFile(null);
  };

  const handleGenerateVoice = async () => {
    if (!voiceText.trim() || isGeneratingVoice || !hasBaseVoice) return;

    setIsGeneratingVoice(true);
    try {
      const response = await apiClient.post<{
        status?: string;
        task_id?: string;
        audio_url?: string;
        s3_url?: string;
        duration?: number;
      }>("/api/v1/tts/generate_voice", {
        text: voiceText,
        influencer_id: params.id,
        base_voice_url: baseVoiceUrl,
      });

      if (response) {
        if (response.status === "pending" && response.task_id) {
          // 비동기 작업인 경우
          toast({
            title: "음성 생성 시작",
            description:
              "음성 생성 작업이 시작되었습니다. 잠시 후 목록에 표시됩니다.",
          });

          // 입력 필드 초기화
          setVoiceText("");

          // 잠시 후 음성 목록 새로고침
          setTimeout(() => {
            loadVoiceHistory();
          }, 5000);
        } else if (response.s3_url) {
          // 동기 작업인 경우 (즉시 완료)
          const newVoice = {
            id: Date.now().toString(),
            text: voiceText,
            url: response.audio_url || response.s3_url,
            duration: response.duration,
            createdAt: new Date().toISOString(),
            status: "completed",
          };
          setVoiceHistory((prev) => [newVoice, ...prev]);

          // 입력 필드 초기화
          setVoiceText("");

          toast({
            title: "음성 생성 완료",
            description: "음성이 성공적으로 생성되었습니다.",
          });

          // 자동 재생 (선택사항)
          handlePlayVoice(response.s3_url);
        }
      }
    } catch (error: any) {
      // console.error("음성 생성 실패:", error);
      toast({
        title: "음성 생성 실패",
        description:
          error.response?.data?.detail || "음성 생성 중 오류가 발생했습니다.",
        variant: "destructive",
      });
    } finally {
      setIsGeneratingVoice(false);
    }
  };

  const checkBaseVoice = async () => {
    try {
      // 베이스 음성 확인 API 호출
      const response = await apiClient.get<{
        base_voice_url: string | null;
        has_voice: boolean;
        message?: string;
      }>(`/api/v1/influencers/${params.id}/voice/base`);

      if (response && response.has_voice && response.base_voice_url) {
        setBaseVoiceUrl(response.base_voice_url);
        setHasBaseVoice(true);
      } else {
        // 음성이 없는 경우
        setHasBaseVoice(false);
        setBaseVoiceUrl(null);
      }
    } catch (error: any) {
      // console.error("베이스 음성 확인 중 오류:", error);
      setHasBaseVoice(false);
      setBaseVoiceUrl(null);
    }
  };

  const loadVoiceHistory = async () => {
    setIsLoadingVoiceHistory(true);
    try {
      const response = await apiClient.get<any[]>(
        `/api/v1/influencers/${params.id}/voices`,
      );

      // response가 배열인지 확인 (apiClient는 데이터를 직접 반환)
      if (Array.isArray(response)) {
        // 응답 데이터를 프론트엔드 형식에 맞게 변환
        const voiceHistory = response.map((voice: any) => ({
          id: voice.id,
          text: voice.text,

          url: voice.audio_url || voice.s3_url, // url 필드를 우선 사용

          duration: voice.duration,
          createdAt: voice.createdAt || voice.created_at, // createdAt 필드를 우선 사용
          status: voice.status || "completed",
          task_id: voice.task_id,
        }));

        setVoiceHistory(voiceHistory);
      } else if (
        (response as any)?.data &&
        Array.isArray((response as any).data)
      ) {
        // response.data가 배열인 경우
        const voiceHistory = (response as any).data.map((voice: any) => ({
          id: voice.id,
          text: voice.text,
          url: voice.audio_url || voice.s3_url,
          duration: voice.duration,
          createdAt: voice.createdAt || voice.created_at,
          status: voice.status || "completed",
          task_id: voice.task_id,
        }));

        setVoiceHistory(voiceHistory);
      } else {
        // 빈 배열로 설정
        setVoiceHistory([]);
      }
    } catch (error) {
      // console.error("음성 목록 로드 실패:", error);
      // 에러가 발생한 경우에만 실패 메시지 표시
      toast({
        title: "로드 실패",
        description: "음성 목록을 불러오는데 실패했습니다.",
        variant: "destructive",
      });
      setVoiceHistory([]);
    } finally {
      setIsLoadingVoiceHistory(false);
    }
  };

  const handlePlayVoice = (url: string) => {
    if (!url) return;

    if (playingVoiceUrl === url && audioRef.current) {
      // 이미 재생 중이면 정지
      audioRef.current.pause();
      setPlayingVoiceUrl(null);
    } else {
      // 이전 오디오가 재생 중이면 정지
      if (audioRef.current) {
        audioRef.current.pause();
      }

      // 새로운 오디오 재생
      const audio = new Audio(url);
      audioRef.current = audio;

      audio
        .play()
        .then(() => {
          setPlayingVoiceUrl(url);
        })
        .catch((error) => {
          // console.error("오디오 재생 실패:", error);
          toast({
            title: "재생 실패",
            description: "오디오를 재생할 수 없습니다.",
            variant: "destructive",
          });
        });

      // 재생이 끝나면 상태 초기화
      audio.addEventListener("ended", () => {
        setPlayingVoiceUrl(null);
      });

      // 에러 발생 시 상태 초기화
      audio.addEventListener("error", () => {
        setPlayingVoiceUrl(null);
        toast({
          title: "재생 오류",
          description: "오디오 파일을 로드할 수 없습니다.",
          variant: "destructive",
        });
      });
    }
  };

  const handleDownloadVoice = async (url: string | undefined, id: string) => {
    try {
      if (!url) {
        throw new Error("음성 파일 URL이 없습니다");
      }

      // console.log("Download URL:", url);

      // 다운로드 시작 알림
      toast({
        title: "다운로드 시작",
        description: "음성 파일을 다운로드하고 있습니다...",
      });

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`다운로드 실패: ${response.status}`);
      }

      // 파일 크기 가져오기
      const contentLength = response.headers.get("content-length");
      const total = parseInt(contentLength || "0", 10);
      // ReadableStream을 사용해서 데이터 읽기
      const reader = response.body?.getReader();
      if (!reader) throw new Error("스트림을 읽을 수 없습니다");

      const chunks: Uint8Array[] = [];
      let receivedLength = 0;

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        chunks.push(value);
        receivedLength += value.length;

        // 진행률 로그 (필요시 UI에 표시 가능)
        if (total) {
          const progress = Math.round((receivedLength / total) * 100);
          // console.log(`다운로드 진행률: ${progress}%`);
        }
      }

      // Uint8Array로 합치기
      const chunksAll = new Uint8Array(receivedLength);
      let position = 0;
      for (const chunk of chunks) {
        chunksAll.set(chunk, position);
        position += chunk.length;
      }

      // Blob 생성 및 다운로드
      const blob = new Blob([chunksAll], { type: "audio/mpeg" });
      const downloadUrl = window.URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = `voice_${id}.mp3`;
      document.body.appendChild(link);
      link.click();

      // 정리
      document.body.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);

      toast({
        title: "다운로드 완료",
        description: "음성 파일이 다운로드되었습니다.",
      });
    } catch (error: any) {
      // console.error("다운로드 실패:", error);
      toast({
        title: "다운로드 실패",
        description: error.message || "음성 파일 다운로드에 실패했습니다.",
        variant: "destructive",
      });
    }
  };

  const handleDeleteVoice = async () => {
    if (!voiceToDelete) return;

    try {
      // 올바른 엔드포인트 경로로 수정
      await apiClient.delete(`/api/v1/influencers/voices/${voiceToDelete}`);

      // 로컬에서 제거
      setVoiceHistory((prev) => prev.filter((v) => v.id !== voiceToDelete));

      toast({
        title: "삭제 완료",
        description: "음성이 삭제되었습니다.",
      });

      setVoiceToDelete(null);
    } catch (error: any) {
      // console.error("음성 삭제 실패:", error);
      toast({
        title: "삭제 실패",
        description:
          error.response?.data?.detail || "음성 삭제에 실패했습니다.",
        variant: "destructive",
      });
    }
  };

  // model이 null이거나 로딩 중이면 로딩 메시지 표시
  if (isModelLoading || !model) {
    return (
      <div className="flex items-center justify-center min-h-[300px] text-gray-500 text-lg">
        로딩 중...
      </div>
    );
  }

  // console.log("[render] model.image_url:", model.image_url);

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <Link
            href="/dashboard"
            className="inline-flex items-center text-blue-600 hover:text-blue-800 mb-4"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            대시보드로 돌아가기
          </Link>
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">{model.name}</h1>
              <p className="text-gray-600 mt-2">{model.description}</p>
              <div className="flex items-center space-x-4 mt-4">
                <Badge
                  className={
                    model.learning_status === 1
                      ? "bg-green-100 text-green-800"
                      : model.learning_status === 0
                        ? "bg-yellow-100 text-yellow-800"
                        : "bg-red-100 text-red-800"
                  }
                >
                  {model.learning_status === 1
                    ? "사용 가능"
                    : model.learning_status === 0
                      ? "생성 중"
                      : "오류"}
                </Badge>
                <span className="text-sm text-gray-500">
                  생성일: {model.createdAt}
                </span>
              </div>
            </div>
            <div className="flex space-x-2">
              {model.learning_status === 1 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={
                    model.chatbot_option
                      ? () => window.open(`/chat/${model.id}`, "_blank")
                      : handleChatbotToggle
                  }
                >
                  <MessageSquare className="h-4 w-4 mr-2" />
                  {model.chatbot_option ? "챗봇 페이지로 이동" : "챗봇 생성"}
                </Button>
              )}
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="destructive" size="sm">
                    <Trash2 className="h-4 w-4 mr-2" />
                    모델 삭제
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>모델 삭제 확인</AlertDialogTitle>
                    <AlertDialogDescription>
                      "{model.name}" 모델을 완전히 삭제하시겠습니까?
                      <br />
                      <br />
                      <strong>
                        이 작업은 되돌릴 수 없으며, 다음 데이터가 모두
                        삭제됩니다:
                      </strong>
                      <br />• 모든 게시글 및 콘텐츠
                      <br />• API 키 및 설정
                      <br />• 학습 데이터 및 모델 정보
                      <br />• 분석 데이터 및 통계
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>취소</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={handleDeleteModel}
                      className="bg-red-600 hover:bg-red-700"
                    >
                      영구 삭제
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </div>
        </div>

        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className="space-y-6"
        >
          <ModelTabsList />

          {/* 분석 탭 */}
          <TabsContent value="analytics">
            <AnalyticsTab
              model={model}
              analyticsData={analyticsData}
              weeklyChartData={weeklyChartData}
              platformStats={platformStats}
              isPostsLoading={isPostsLoading}
              loadAnalyticsData={loadAnalyticsData}
              getPlatformBadge={getPlatformBadge}
            />
          </TabsContent>

          {/* 콘텐츠 탭 */}
          <TabsContent value="content">
            <ContentTab
              posts={posts}
              isPostsLoading={isPostsLoading}
              loadPostsData={loadPostsData}
              handleViewPostDetail={handleViewPostDetail}
              PostCard={PostCard}
            />
          </TabsContent>

          {/* API 탭 */}
          <TabsContent value="api">
            <ApiTab
              model={model}
              showApiKey={showApiKey}
              setShowApiKey={setShowApiKey}
              isGeneratingApiKey={isGeneratingApiKey}
              copyApiKey={copyApiKey}
              generateNewApiKey={generateNewApiKey}
              apiKeyInfo={apiKeyInfo}
            />
          </TabsContent>

          {/* 연동 탭 */}
          <TabsContent value="integrations">
            <IntegrationsTab
              instagramStatus={instagramStatus}
              isConnecting={isConnecting}
              handleInstagramConnect={handleInstagramConnect}
              handleInstagramDisconnect={handleInstagramDisconnect}
              PostImage={PostImage}
            />
          </TabsContent>

          {/* 정보 탭 */}
          <TabsContent value="settings">
            <SettingsTab
              model={model}
              setModel={setModel}
              isModelLoading={isModelLoading}
              isUpdating={isUpdating}
              isUploadingImage={isUploadingImage}
              uploadedImage={uploadedImage}
              imagePreview={imagePreview}
              openImageModal={openImageModal}
              openGalleryModal={openGalleryModal}
              handleImageUpload={handleImageUpload}
              handleUpdateModel={handleUpdateModel}
            />
          </TabsContent>

          {/* 음성 탭 */}
          <TabsContent value="voice">
            <VoiceTab
              hasBaseVoice={hasBaseVoice}
              baseVoiceUrl={baseVoiceUrl}
              baseVoiceFile={baseVoiceFile}
              setBaseVoiceFile={setBaseVoiceFile}
              isUploadingBaseVoice={isUploadingBaseVoice}
              voiceText={voiceText}
              setVoiceText={setVoiceText}
              isGeneratingVoice={isGeneratingVoice}
              voiceHistory={voiceHistory}
              isLoadingVoiceHistory={isLoadingVoiceHistory}
              playingVoiceUrl={playingVoiceUrl}
              setVoiceToDelete={setVoiceToDelete}
              handlePlayVoice={handlePlayVoice}
              handleChangeBaseVoice={handleChangeBaseVoice}
              handleBaseVoiceFileSelect={handleBaseVoiceFileSelect}
              handleUploadBaseVoice={handleUploadBaseVoice}
              handleGenerateVoice={handleGenerateVoice}
              loadVoiceHistory={loadVoiceHistory}
              handleDownloadVoice={handleDownloadVoice}
              toast={toast}
            />
          </TabsContent>

          {/* MCP 탭 */}
          <TabsContent value="mcp">
            <McpTab
              model={model}
              MCPServerSelector={MCPServerSelector}
            />
          </TabsContent>
        </Tabs>

        {/* 게시글 상세 보기 모달 */}
        <Dialog
          open={isPostDetailModalOpen}
          onOpenChange={setIsPostDetailModalOpen}
        >
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center space-x-2">
                <Eye className="h-5 w-5" />
                <span>게시글 상세 보기</span>
              </DialogTitle>
              <div className="flex items-center space-x-2">
                {(selectedPost?.status === "draft" ||
                  selectedPost?.status === "scheduled") && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setIsEditing(!isEditing)}
                      className="flex items-center space-x-1"
                    >
                      {isEditing ? (
                        <>
                          <Eye className="h-4 w-4" />
                          <span>보기 모드</span>
                        </>
                      ) : (
                        <>
                          <Edit className="h-4 w-4" />
                          <span>수정 모드</span>
                        </>
                      )}
                    </Button>
                  )}
                {isEditing && (
                  <Button
                    onClick={handleEditSave}
                    size="sm"
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    저장
                  </Button>
                )}
                {selectedPost?.instagram_link && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      window.open(selectedPost.instagram_link, "_blank")
                    }
                    className="flex items-center space-x-1"
                  >
                    <ExternalLink className="h-4 w-4" />
                    <span>인스타그램 보기</span>
                  </Button>
                )}
              </div>
            </DialogHeader>

            {selectedPost && (
              <div className="space-y-6">
                {/* 게시글 기본 정보 */}
                <div className="flex justify-between items-start pb-4 border-b">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 mb-2">
                      {selectedPost.title}
                    </h3>
                    {/* 인플루언서 정보 */}
                    <div className="flex items-center space-x-2 text-sm text-gray-500 mt-1">
                      <div className="w-5 h-5 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center">
                        <span className="text-white text-xs font-medium">
                          AI
                        </span>
                      </div>
                      <span className="font-medium text-gray-700">
                        {selectedPost.influencerName ||
                          model?.name ||
                          "AI 인플루언서"}
                      </span>
                      {selectedPost.influencerDescription && (
                        <span className="text-gray-500">
                          • {selectedPost.influencerDescription}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center space-x-2 text-sm text-gray-500 mt-1">
                      <Calendar className="h-4 w-4" />
                      {selectedPost.status === "scheduled" &&
                        selectedPost.scheduledAt &&
                        selectedPost.scheduledAt.trim() !== "" ? (
                        <span>
                          예약 발행:{" "}
                          {formatDate(selectedPost.scheduledAt || "")}
                        </span>
                      ) : selectedPost.status === "published" &&
                        selectedPost.publishedAt &&
                        selectedPost.publishedAt.trim() !== "" ? (
                        <span>
                          발행: {formatDate(selectedPost.publishedAt || "")}
                        </span>
                      ) : selectedPost.status === "published" ? (
                        <span>발행됨 (날짜 정보 없음)</span>
                      ) : selectedPost.status === "scheduled" ? (
                        <span>예약됨 (날짜 정보 없음)</span>
                      ) : (
                        <span>임시저장</span>
                      )}
                    </div>
                  </div>

                  {/* 오른쪽 상단에 배지들 배치 */}
                  <div className="flex flex-col items-end space-y-2 ml-4">
                    {selectedPost.platform &&
                      getPlatformBadge(selectedPost.platform)}
                    {getStatusBadge(selectedPost.status)}
                  </div>
                </div>

                {/* 게시글 내용 */}
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-gray-900">
                    게시글 내용
                  </h4>
                  {isEditing &&
                    (selectedPost?.status === "draft" ||
                      selectedPost?.status === "scheduled") ? (
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          제목
                        </label>
                        <Input
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          placeholder="게시글 제목을 입력하세요"
                          className="w-full"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          내용
                        </label>
                        <textarea
                          value={editContent}
                          onChange={(e) => setEditContent(e.target.value)}
                          placeholder="게시글 내용을 입력하세요"
                          className="w-full h-32 p-3 border border-gray-300 rounded-md resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          해시태그
                        </label>
                        <Input
                          value={editHashtags}
                          onChange={(e) => setEditHashtags(e.target.value)}
                          placeholder="#해시태그1 #해시태그2"
                          className="w-full"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          예약 시간
                        </label>
                        <Input
                          type="datetime-local"
                          value={editScheduledAt}
                          onChange={(e) => setEditScheduledAt(e.target.value)}
                          className="w-full"
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="bg-gray-50 border rounded-lg p-4">
                      <div className="whitespace-pre-wrap text-gray-800 leading-relaxed">
                        {selectedPost.content}
                      </div>
                    </div>
                  )}
                </div>

                {/* 해시태그 */}
                {!isEditing && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-gray-900">
                      해시태그
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {selectedPost.hashtags?.map((tag, index) => (
                        <span
                          key={index}
                          className="text-sm text-blue-600 bg-blue-50 px-3 py-1 rounded-full"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* 미디어 정보 */}
                {selectedPost.media && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-gray-900">
                      미디어
                    </h4>
                    <div className="bg-gray-50 border rounded-lg p-4">
                      <div className="flex items-center space-x-2 mb-2">
                        <span className="text-sm font-medium text-gray-700">
                          {selectedPost.media.type === "image" && "이미지"}
                          {selectedPost.media.type === "video" && "비디오"}
                          {selectedPost.media.type === "carousel" && "이미지"}
                        </span>
                        {selectedPost.media.type === "carousel" && (
                          <Badge variant="outline" className="text-xs">
                            {selectedPost.media.urls.length}개 파일
                          </Badge>
                        )}
                      </div>
                      {selectedPost.media.urls && selectedPost.media.urls.length > 0 && (
                        <div className="mt-2">
                          {selectedPost.media.urls.length === 1 ? (
                            // 단일 이미지
                            <img
                              src={selectedPost.media.urls[0]}
                              alt="미디어"
                              className="w-32 h-32 object-cover rounded-lg border"
                            />
                          ) : (
                            // 다중 이미지 캐러셀
                            <div className="relative">
                              <div className="flex items-center justify-between absolute inset-0 z-10">
                                <button
                                  onClick={() => {
                                    const urls = selectedPost.media?.urls ?? [];
                                    if (urls.length === 0) return;
                                    const currentIndex = carouselIndices[selectedPost.id || ''] || 0;
                                    const newIndex = currentIndex > 0 ? currentIndex - 1 : urls.length - 1;
                                    setCarouselIndices(prev => ({
                                      ...prev,
                                      [selectedPost.id || '']: newIndex
                                    }));
                                  }}
                                  className="bg-black bg-opacity-50 text-white p-1 rounded-full hover:bg-opacity-70 transition-all"
                                >
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                                  </svg>
                                </button>
                                <button
                                  onClick={() => {
                                    const urls = selectedPost.media?.urls ?? [];
                                    if (urls.length === 0) return;
                                    const currentIndex = carouselIndices[selectedPost.id || ''] || 0;
                                    const newIndex = currentIndex < urls.length - 1 ? currentIndex + 1 : 0;
                                    setCarouselIndices(prev => ({
                                      ...prev,
                                      [selectedPost.id || '']: newIndex
                                    }));
                                  }}
                                  className="bg-black bg-opacity-50 text-white p-1 rounded-full hover:bg-opacity-70 transition-all"
                                >
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                  </svg>
                                </button>
                              </div>
                              <img
                                src={selectedPost.media.urls[carouselIndices[selectedPost.id || ''] || 0]}
                                alt={`미디어 ${(carouselIndices[selectedPost.id || ''] || 0) + 1}`}
                                className="w-32 h-32 object-cover rounded-lg border"
                              />
                              {/* 인디케이터 */}
                              <div className="flex justify-center mt-2 space-x-1">
                                {selectedPost.media.urls.map((_, index) => (
                                  <button
                                    key={index}
                                    onClick={() => {
                                      setCarouselIndices(prev => ({
                                        ...prev,
                                        [selectedPost.id || '']: index
                                      }));
                                    }}
                                    className={`w-2 h-2 rounded-full transition-all ${index === (carouselIndices[selectedPost.id || ''] || 0)
                                      ? 'bg-blue-500'
                                      : 'bg-gray-300'
                                      }`}
                                  />
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 성과 지표 */}
                {selectedPost.status === "published" &&
                  selectedPost.engagement && (
                    <div className="space-y-2">
                      <h4 className="text-sm font-medium text-gray-900">
                        성과 지표
                      </h4>
                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="grid grid-cols-2 gap-4">
                          <div className="text-center">
                            <div className="flex items-center justify-center space-x-2 mb-1">
                              <Heart className="h-5 w-5 text-red-500" />
                              <span className="text-lg font-bold text-gray-900">
                                {selectedPost.engagement.likes.toLocaleString()}
                              </span>
                            </div>
                            <p className="text-sm text-gray-600">좋아요</p>
                          </div>
                          <div className="text-center">
                            <div className="flex items-center justify-center space-x-2 mb-1">
                              <MessageCircle className="h-5 w-5 text-blue-500" />
                              <span className="text-lg font-bold text-gray-900">
                                {selectedPost.engagement.comments.toLocaleString()}
                              </span>
                            </div>
                            <p className="text-sm text-gray-600">댓글</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                {/* 플랫폼별 미리보기 */}
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-gray-900">
                    플랫폼 미리보기
                  </h4>
                  <div className="bg-gray-50 border rounded-lg p-4">
                    {renderPlatformSpecificPost(selectedPost)}
                  </div>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* 이미지 모달 */}
        <Dialog open={isImageModalOpen} onOpenChange={setIsImageModalOpen}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle className="flex items-center space-x-2">
                <img src="/favicon.ico" alt="AI Influencer" className="h-5 w-5" />
                <span>프로필 이미지</span>
              </DialogTitle>
            </DialogHeader>

            <div className="space-y-6">
              {/* 현재 이미지 표시 */}
              <div className="flex justify-center">
                {uploadedImage && imagePreview ? (
                  <div className="relative">
                    <img
                      src={imagePreview}
                      alt="Uploaded"
                      className="w-80 h-80 object-cover rounded-lg shadow-lg"
                    />
                  </div>
                ) : model?.image_url ? (
                  <div className="relative">
                    <img
                      src={model.image_url}
                      alt="Profile"
                      className="w-80 h-80 object-cover rounded-lg shadow-lg"
                      key={model.image_url}
                      onError={() => setImgError(true)}
                    />
                  </div>
                ) : (
                  <div className="w-80 h-80 rounded-lg bg-gradient-to-br from-blue-200 to-blue-50 flex items-center justify-center shadow-lg">
                    <img src="/favicon.ico" alt="AI Influencer" className="h-20 w-20" />
                  </div>
                )}
              </div>

              {/* 이미지 정보 */}
              <div className="text-center space-y-2">
                <p className="text-sm text-gray-600">
                  권장 크기: 400x400px, 최대 5MB
                </p>
                <p className="text-xs text-gray-400">JPG, PNG 형식 지원</p>
              </div>

              {/* 액션 버튼들 */}
              <div className="flex justify-center space-x-4">
                {/* 파일 업로드 버튼 */}
                <input
                  id="modal-image-upload"
                  type="file"
                  accept="image/*"
                  onChange={handleImageUpload}
                  className="hidden"
                />
                <Button
                  variant="outline"
                  className="flex items-center space-x-2"
                  onClick={() =>
                    document.getElementById("modal-image-upload")?.click()
                  }
                >
                  <Upload className="h-4 w-4" />
                  <span>이미지 업로드</span>
                </Button>

                {/* 갤러리에서 불러오기 버튼 */}
                <Button
                  variant="outline"
                  onClick={openGalleryModal}
                  className="flex items-center space-x-2"
                >
                  <ImageIcon className="h-4 w-4" />
                  <span>갤러리에서 불러오기</span>
                </Button>
              </div>

              {/* 저장 버튼과 제거 버튼 - 변경사항이 있을 때만 표시 */}
              {hasImageChanges && (
                <div className="flex justify-center space-x-4 pt-4 border-t">
                  <Button
                    onClick={async () => {
                      await handleUpdateModel();
                      setIsImageModalOpen(false);
                    }}
                    disabled={isUpdating || isModelLoading || isUploadingImage}
                    className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-8"
                  >
                    {isUploadingImage
                      ? "업로드 중..."
                      : isUpdating
                        ? "저장 중..."
                        : isModelLoading
                          ? "로딩 중..."
                          : "저장"}
                  </Button>

                  {/* 이미지 제거 버튼 (업로드된 이미지가 있을 때만) */}
                  {uploadedImage && imagePreview && (
                    <Button
                      variant="outline"
                      onClick={removeImage}
                      className="text-red-600 border-red-200 hover:bg-red-50 px-8"
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      제거
                    </Button>
                  )}
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>

        {/* 갤러리 모달 */}
        <Dialog open={isGalleryModalOpen} onOpenChange={setIsGalleryModalOpen}>
          <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center space-x-2">
                <ImageIcon className="h-5 w-5" />
                <span>갤러리에서 이미지 선택</span>
              </DialogTitle>
            </DialogHeader>

            <div className="space-y-6">
              {isLoadingGallery ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
                  <span className="ml-2 text-gray-600">
                    이미지 목록을 불러오는 중...
                  </span>
                </div>
              ) : galleryImages.length > 0 ? (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {galleryImages.map((imageUrl, index) => (
                    <div
                      key={index}
                      className="relative group cursor-pointer"
                      onClick={() => selectGalleryImage(imageUrl)}
                    >
                      <img
                        src={imageUrl}
                        alt={`Gallery image ${index + 1}`}
                        className="w-full h-32 object-cover rounded-lg border hover:border-blue-500 transition-colors"
                      />
                      <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-30 transition-all duration-200 rounded-lg flex items-center justify-center">
                        <span className="text-white opacity-0 group-hover:opacity-100 text-sm font-medium">
                          선택
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <ImageIcon className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                  <p className="text-gray-500 text-lg">
                    갤러리에 이미지가 없습니다
                  </p>
                  <p className="text-gray-400 mt-2">
                    먼저 이미지를 업로드해주세요
                  </p>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>

        <Dialog
          open={!!voiceToDelete}
          onOpenChange={(open) => !open && setVoiceToDelete(null)}
        >
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle>음성 삭제 확인</DialogTitle>
              <DialogDescription>
                이 음성을 삭제하시겠습니까? 삭제된 음성은 복구할 수 없습니다.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setVoiceToDelete(null)}>
                취소
              </Button>
              <Button variant="destructive" onClick={handleDeleteVoice}>
                삭제
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* 갤러리 모달 */}
      <Dialog open={isGalleryModalOpen} onOpenChange={setIsGalleryModalOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>갤러리에서 이미지 선택</DialogTitle>
            <DialogDescription>
              생성된 이미지 중에서 프로필 이미지로 사용할 이미지를 선택하세요.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4">
            {/* 이미지 그리드 */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {galleryImages.map((image) => (
                <div
                  key={image.storage_id}
                  className="relative cursor-pointer group"
                  onClick={() => selectGalleryImage(image.s3_url)}
                >
                  <div className="aspect-square rounded-lg overflow-hidden border border-gray-200 hover:border-blue-500 transition-colors">
                    <img
                      src={image.s3_url}
                      alt={image.prompt || 'Gallery image'}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
                    />
                  </div>
                  <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-20 transition-all duration-200 rounded-lg flex items-center justify-center">
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                      <span className="text-white text-sm font-medium">선택</span>
                    </div>
                  </div>
                  <div className="mt-2">
                    <p className="text-sm text-gray-600 line-clamp-2">
                      {image.prompt || '이미지 설명 없음'}
                    </p>
                    <div className="flex justify-between items-center text-xs text-gray-500 mt-1">
                      <span>{image.width} × {image.height}</span>
                      <span>{new Date(image.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            
            {galleryImages.length === 0 && !isLoadingGallery && (
              <div className="text-center py-12">
                <ImageIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-lg font-medium text-gray-900 mb-2">생성된 이미지가 없습니다</p>
                <p className="text-gray-600">먼저 이미지를 생성해보세요</p>
              </div>
            )}
            
            {isLoadingGallery && (
              <div className="text-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600">이미지를 불러오는 중...</p>
              </div>
            )}
            
            {/* 페이지네이션 */}
            {galleryTotalPages > 1 && (
              <div className="flex justify-center items-center gap-2 mt-6 pt-4 border-t">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleGalleryPageChange(galleryCurrentPage - 1)}
                  disabled={galleryCurrentPage <= 1}
                  className="flex items-center gap-1"
                >
                  <ChevronLeft className="h-4 w-4" />
                  이전
                </Button>
                
                <div className="flex items-center gap-1">
                  {Array.from({ length: Math.min(5, galleryTotalPages) }, (_, i) => {
                    let pageNum
                    if (galleryTotalPages <= 5) {
                      pageNum = i + 1
                    } else if (galleryCurrentPage <= 3) {
                      pageNum = i + 1
                    } else if (galleryCurrentPage >= galleryTotalPages - 2) {
                      pageNum = galleryTotalPages - 4 + i
                    } else {
                      pageNum = galleryCurrentPage - 2 + i
                    }
                    
                    return (
                      <Button
                        key={pageNum}
                        variant={galleryCurrentPage === pageNum ? "default" : "outline"}
                        size="sm"
                        onClick={() => handleGalleryPageChange(pageNum)}
                        className="w-8 h-8 p-0"
                      >
                        {pageNum}
                      </Button>
                    )
                  })}
                </div>
                
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleGalleryPageChange(galleryCurrentPage + 1)}
                  disabled={galleryCurrentPage >= galleryTotalPages}
                  className="flex items-center gap-1"
                >
                  다음
                  <ChevronRight className="h-4 w-4" />
                </Button>
                
                <span className="text-sm text-gray-500 ml-2">
                  {galleryCurrentPage} / {galleryTotalPages} 페이지
                </span>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* 토스트 알림 컴포넌트 */}
      <Toaster />
    </div>
  );
}

// MCPServerSelector 함수 정의를 export default ModelDetailPage 위로 이동

const MCPServerSelector: FC<{ influencerId: string; model: any }> = ({
  influencerId,
  model,
}) => {
  const { toast } = useToast();
  const [servers, setServers] = useState<any[]>([]); // 배열로 변경
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [originalSelected, setOriginalSelected] = useState<string[]>([]);

  // MCP 서버 추가 관련 상태
  const [addName, setAddName] = useState(""); // HTTP 방식에서만 사용
  const [addType, setAddType] = useState<"http" | "stdio">("stdio");
  // HTTP 방식
  const [addHttpUrl, setAddHttpUrl] = useState("");
  // STDIO 방식
  const [addStdioJson, setAddStdioJson] = useState("");
  const [addDesc, setAddDesc] = useState("");
  const [addLoading, setAddLoading] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [addSuccess, setAddSuccess] = useState(false);
  // MCP 서버 추가 폼 접힘 상태
  const [addOpen, setAddOpen] = useState(false);
  // MCP 서버 제거 관련 상태
  const [removingServer, setRemovingServer] = useState<string | null>(null);
  const [serverToRemove, setServerToRemove] = useState<string | null>(null);

  const loadServers = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await MCPService.getServers();
      const serverArr = Object.values(res.servers) || [];
      setServers(serverArr);
      // 연결된 서버 체크박스 자동 선택
      if (model && model.name) {
        const checked = (serverArr as any[])
          .filter(
            (server) =>
              Array.isArray((server as any).connected_influencers) &&
              (server as any).connected_influencers.includes(model.name),
          )
          .map((server) => (server as any).mcp_name);
        setSelected(checked);
        setOriginalSelected(checked); // 기존 설정 저장
      }
      setLoading(false);
    } catch (e: any) {
      setError(e.message || "서버 목록을 불러오지 못했습니다.");
      setLoading(false);
    }
  };

  // 초기 로드
  useEffect(() => {
    loadServers();
  }, []); // 컴포넌트 마운트 시 한 번만 실행

  // 서버 추가/제거 후 새로고침
  useEffect(() => {
    if (addSuccess) {
      loadServers();
      setAddSuccess(false); // 새로고침 후 플래그 리셋
    }
  }, [addSuccess]);

  const handleToggle = (name: string) => {
    setSelected((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name],
    );
  };

  const handleGoChatbot = async () => {
    if (selected.length === 0) return;

    try {
      // 백엔드에 선택된 서버 정보 전송
      const response = await fetch("/api/v1/mcp/chat/set-selected-servers", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          influencer_id: influencerId,
          selected_servers: selected,
        }),
      });

      if (response.ok) {
        // console.log("선택된 MCP 서버 정보를 백엔드에 전송 완료:", selected);
        // 쿼리 스트링 없이 챗봇 페이지로 이동
        window.open(`/chat/${influencerId}`, "_blank");
      } else {
        // console.error("서버 정보 전송 실패");
      }
    } catch (error) {
      // console.error("서버 정보 전송 중 오류:", error);
    }
  };

  const handleAddServer = async () => {
    setAddLoading(true);
    setAddError(null);
    setAddSuccess(false);
    try {
      let serverName = "";
      let config: any = {};
      let payload: any = {};
      if (addType === "http") {
        if (!addName.trim()) throw new Error("서버명을 입력하세요.");
        if (!addHttpUrl.trim()) throw new Error("HTTP 서버 URL을 입력하세요.");
        serverName = addName.trim();
        payload = {
          server_name: serverName,
          mcp_status: 1,
          transport: "sse",
          mcp_config: { url: addHttpUrl.trim(), transport: "sse" },
          description: addDesc.trim(),
        };
      } else {
        if (!addStdioJson.trim())
          throw new Error("STDIO 서버 설정 JSON을 입력하세요.");
        let parsed: any;
        try {
          parsed = JSON.parse(addStdioJson);
        } catch (e) {
          throw new Error("유효한 JSON 형식이 아닙니다.");
        }
        const keys = Object.keys(parsed);
        if (keys.length !== 1)
          throw new Error("JSON에 서버명 하나만 포함되어야 합니다.");
        serverName = keys[0];
        config = parsed[serverName];
        payload = {
          server_name: serverName,
          mcp_status: 0,
          transport: "stdio",
          mcp_config: { ...config, transport: "stdio" },
          description: addDesc.trim(),
        };
      }
      const result = await MCPService.addServer(payload);
      if (result.success) {
        setAddSuccess(true);
        setAddName("");
        setAddHttpUrl("");
        setAddStdioJson("");
        setAddDesc("");
        toast({
          title: "MCP 서버 추가 성공",
          description:
            result.message || "MCP 서버가 성공적으로 추가되었습니다.",
        });
        setTimeout(() => setAddSuccess(false), 1500);
      } else {
        setAddError(result.message || "서버 추가에 실패했습니다.");
        toast({
          title: "MCP 서버 추가 실패",
          description: result.message || "서버 추가에 실패했습니다.",
          variant: "destructive",
        });
      }
    } catch (e: any) {
      const errorMessage = e?.message || "서버 추가에 실패했습니다.";
      setAddError(errorMessage);
      toast({
        title: "MCP 서버 추가 실패",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setAddLoading(false);
    }
  };

  const handleSaveSelection = async () => {
    try {
      await apiClient.post("/api/v1/mcp/chat/set-selected-servers", {
        influencer_id: influencerId,
        selected_servers: selected,
      });
      setOriginalSelected([...selected]); // 저장 후 기존 설정 업데이트
      toast({
        title: "MCP 서버 설정 저장",
        description: "MCP 서버 설정이 저장되었습니다.",
      });
      // 설정 저장 후 MCP 목록 새로고침
      setAddSuccess(true); // Triggers useEffect to reload servers
    } catch (error) {
      toast({
        title: "MCP 서버 설정 저장 실패",
        description: "설정 저장에 실패했습니다.",
      });
    }
  };

  const handleRemoveServer = async (serverName: string) => {
    if (!serverName) return;

    setRemovingServer(serverName);
    try {
      const result = await MCPService.removeServer(serverName);
      if (result.success) {
        toast({
          title: "MCP 서버 제거 성공",
          description: result.message || "MCP 서버가 성공적으로 제거되었습니다.",
        });
        // 서버 목록 새로고침
        setAddSuccess(true);
        // 선택된 서버에서도 제거
        setSelected(prev => prev.filter(name => name !== serverName));
      } else {
        toast({
          title: "MCP 서버 제거 실패",
          description: result.message || "서버 제거에 실패했습니다.",
          variant: "destructive",
        });
      }
    } catch (error) {
      toast({
        title: "MCP 서버 제거 실패",
        description: "서버 제거 중 오류가 발생했습니다.",
        variant: "destructive",
      });
    } finally {
      setRemovingServer(null);
    }
  };

  if (loading)
    return <div className="py-8 text-gray-400">서버 목록을 불러오는 중...</div>;
  if (error) return <div className="py-8 text-red-500">{error}</div>;
  const serverNames = Object.keys(servers);

  return (
    <div className="max-w-md mx-auto text-left">
      <div className="mb-6">
        <button
          className="w-full flex items-center justify-between p-4 border rounded-lg bg-gray-50 font-semibold hover:bg-gray-100 transition-all mb-2"
          onClick={() => setAddOpen((v) => !v)}
          type="button"
        >
          <span>외부 MCP 서버 추가</span>
          <span
            className={`transition-transform ${addOpen ? "rotate-90" : ""}`}
          >
            ▶
          </span>
        </button>
        {addOpen && (
          <div className="p-4 border rounded-lg bg-gray-50 mt-0">
            <div className="flex gap-4 mb-2">
              <label className="flex items-center gap-1">
                <input
                  type="radio"
                  checked={addType === "stdio"}
                  onChange={() => setAddType("stdio")}
                />
                <span>STDIO 방식</span>
              </label>
              <label className="flex items-center gap-1">
                <input
                  type="radio"
                  checked={addType === "http"}
                  onChange={() => setAddType("http")}
                />
                <span>SSE 방식</span>
              </label>
            </div>
            {addType === "http" ? (
              <>
                <Input
                  placeholder="서버명"
                  value={addName}
                  onChange={(e) => setAddName(e.target.value)}
                  className="mb-2"
                />
                <Input
                  placeholder="HTTP 서버 URL (예: http://localhost:9000)"
                  value={addHttpUrl}
                  onChange={(e) => setAddHttpUrl(e.target.value)}
                  className="mb-2"
                />
              </>
            ) : (
              <>
                <div className="mb-2 p-2 bg-blue-50 border border-blue-200 rounded text-xs text-blue-800">
                  <strong>💡 OS별 명령어 경로 안내:</strong>
                  <br />
                  • <strong>Windows:</strong> npx.cmd, node.exe 경로 자동 감지
                  <br />
                  • <strong>Mac/Linux:</strong> PATH에서 npx, node 자동 검색
                  <br />
                  • <strong>NVM 사용 시:</strong> ~/.nvm/versions/node/*/bin/ 경로 자동 감지
                  <br />
                  • <strong>설정 형태:</strong> cmd /c 형태와 직접 npx 형태 모두 지원
                </div>
                <textarea
                  placeholder={`STDIO MCP 서버 설정 JSON 전체를 입력하세요. 예:\n{\n  \"frankfurtermcp\": {\n    \"command\": \"npx\",\n    \"args\": [\"-y\", \"@smithery/cli@latest\", \"run\", \"exa\", \"--key\", \"...\", \"--profile\", \"...\"]\n  }\n}\n\n또는 Windows cmd 형태:\n{\n  \"frankfurtermcp\": {\n    \"command\": \"cmd\",\n    \"args\": [\"/c\", \"npx\", \"-y\", \"@smithery/cli@latest\", \"run\", \"exa\", \"--key\", \"...\", \"--profile\", \"...\"]\n  }\n}`}
                  value={addStdioJson}
                  onChange={(e) => setAddStdioJson(e.target.value)}
                  rows={10}
                  className="w-full border rounded p-2 font-mono text-xs mb-2"
                ></textarea>
              </>
            )}
            <Input
              placeholder="설명(선택)"
              value={addDesc}
              onChange={(e) => setAddDesc(e.target.value)}
              className="mb-2"
            />
            <Button
              onClick={handleAddServer}
              disabled={addLoading}
              className="w-full mb-1"
            >
              {addLoading ? "추가 중..." : "서버 추가"}
            </Button>
            {addError && (
              <div className="text-red-500 text-sm mt-1">{addError}</div>
            )}
          </div>
        )}
      </div>
      <div className="mb-4 text-sm text-gray-600">
        활성화할 MCP 서버를 선택하세요:
      </div>
      <div className="space-y-2 mb-6">
        {servers.map((server) => {
          const name = server.mcp_name;
          const desc =
            server.description || server.mcp_config?.description || "";
          return (
            <label
              key={name}
              className="flex items-center gap-3 p-3 rounded border border-gray-200 hover:bg-gray-50 cursor-pointer transition-all"
            >
              <input
                type="checkbox"
                checked={selected.includes(name)}
                onChange={() => handleToggle(name)}
                disabled={!server.running}
                className="accent-blue-600 mt-1"
              />
              <div className="flex flex-col flex-1 min-w-0">
                <span
                  className={`font-semibold text-base truncate ${server.running ? "text-gray-900" : "text-gray-400 line-through"}`}
                >
                  {name}
                </span>
                {desc && (
                  <span className="text-xs text-gray-500 mt-0.5 truncate">
                    {desc}
                  </span>
                )}
              </div>
              {!server.running && (
                <span className="ml-2 text-xs text-red-400">(중지됨)</span>
              )}
              {/* 제거 버튼 */}
              {server.can_delete && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setServerToRemove(name);
                  }}
                  disabled={removingServer === name}
                  className="text-red-600 hover:text-red-700 hover:bg-red-50"
                >
                  {removingServer === name ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </Button>
              )}
            </label>
          );
        })}
      </div>
      <button
        className={`w-full py-2 rounded bg-gray-800 text-white font-semibold transition-all ${JSON.stringify(selected.sort()) === JSON.stringify(originalSelected.sort())
          ? "opacity-50 cursor-not-allowed"
          : "hover:bg-gray-900"
          }`}
        onClick={handleSaveSelection}
        disabled={JSON.stringify(selected.sort()) === JSON.stringify(originalSelected.sort())}
      >
        설정 저장
      </button>

      {/* MCP 서버 제거 확인 다이얼로그 */}
      <AlertDialog open={!!serverToRemove} onOpenChange={(open) => !open && setServerToRemove(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>MCP 서버 제거 확인</AlertDialogTitle>
            <AlertDialogDescription>
              <span className="block mb-2">
                <strong>"{serverToRemove}"</strong> 서버를 제거하시겠습니까?
              </span>
              <span className="block text-sm text-gray-600">
                이 작업은 되돌릴 수 없으며, 서버와 관련된 모든 설정이 영구적으로 삭제됩니다.
              </span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setServerToRemove(null)}>
              취소
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (serverToRemove) {
                  handleRemoveServer(serverToRemove);
                  setServerToRemove(null);
                }
              }}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              제거
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

const ModelDetailPage: FC = () => {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-gray-50">
          <Navigation />
          <div className="max-w-6xl mx-auto p-8">
            <div className="animate-pulse">
              <div className="h-8 bg-gray-200 rounded w-64 mb-6"></div>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2">
                  <div className="h-96 bg-gray-200 rounded-lg"></div>
                </div>
                <div>
                  <div className="h-64 bg-gray-200 rounded-lg"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      }
    >
      <ModelDetailContent />
    </Suspense>
  );
};

export default ModelDetailPage;
