"use client"

import { useState, useEffect, useRef, Suspense } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Navigation } from "@/components/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
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
} from "@/components/ui/alert-dialog"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Plus, Search, Edit, Trash2, Eye, Calendar, User, Filter, X, Copy, ExternalLink, Heart, MessageCircle, MoreHorizontal, UploadCloud, Instagram, Users, BarChart3, Bookmark } from "lucide-react"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import apiClient from "@/lib/api"
import { useToast } from "@/hooks/use-toast"
import { InstagramPostingService } from "@/lib/services/instagram-posting.service"
import { PostCard, Post } from "@/components/ui/post-card"
import { convertUTCToKST, formatDateKorean, getRelativeTime } from "@/lib/utils/timezone"





function PostListContent() {
  const [posts, setPosts] = useState<Post[]>([])
  const [loading, setLoading] = useState(true)
  const { toast } = useToast()
  const [searchTerm, setSearchTerm] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [modelFilter, setModelFilter] = useState<string>("all")
  const [platformFilter, setPlatformFilter] = useState<string[]>([])

  // 임시 필터 상태 (모달에서 사용)
  const [tempStatusFilter, setTempStatusFilter] = useState<string>("all")
  const [tempModelFilter, setTempModelFilter] = useState<string>("all")
  const [tempPlatformFilter, setTempPlatformFilter] = useState<string[]>([])
  const [isFilterModalOpen, setIsFilterModalOpen] = useState(false)

  // 게시글 상세 보기 모달 상태
  const [selectedPost, setSelectedPost] = useState<Post | null>(null)
  const [isViewModalOpen, setIsViewModalOpen] = useState(false)
  const [editMode, setEditMode] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const [editHashtags, setEditHashtags] = useState("");
  const [editScheduledAt, setEditScheduledAt] = useState("");
  const [isSaving, setIsSaving] = useState(false);



  const searchParams = useSearchParams()
  const hasAddedNewPost = useRef(false)
  const router = useRouter()

  // API에서 게시글 목록 가져오기
  const fetchPosts = async () => {
    try {
      setLoading(true)

      const boardData = await apiClient.get<any[]>('/api/v1/boards')

      // 각 게시글에 대해 인스타그램 통계 정보 가져오기
      const transformedPosts: Post[] = await Promise.all(
        boardData.map(async (board: any) => {
          // 인플루언서 정보 조회
          let influencerName = 'AI 인플루언서'
          let influencerDescription = ''

          if (board.influencer_id) {
            try {
              const influencerResponse = await apiClient.get(`/api/v1/influencers/${board.influencer_id}`)
              if (influencerResponse) {
                influencerName = influencerResponse.influencer_name || 'AI 인플루언서'
                influencerDescription = influencerResponse.influencer_description || ''
              }
            } catch (error) {
            }
          }

          const basePost = {
            ...board,
            id: board.board_id,
            title: board.board_topic,
            content: board.board_description,
            createdAt: board.created_at,
            platform: getPlatformName(board.board_platform),
            hashtags: board.board_hash_tag ? board.board_hash_tag.split(' ').filter((tag: string) => tag.trim()).map((tag: string) => tag.startsWith('#') ? tag : `#${tag}`) : [],
            status: getStatusName(board.board_status),
            author: influencerName,
            modelName: influencerName,
            scheduledAt: board.reservation_at,
            publishedAt: board.published_at,
            // 인플루언서 정보: 별도 조회한 값 사용
            influencerName: influencerName,
            influencerDescription: influencerDescription,
            media: {
              type: "image" as const,
              urls: [board.image_url || "/placeholder.svg?height=400&width=400"],
              thumbnailUrl: board.image_url || "/placeholder.svg?height=400&width=400"
            }
          }

          // 백엔드에서 제공하는 인스타그램 통계 사용
          const instagramStats = board.instagram_stats || {
            like_count: 0,
            comments_count: 0,
            impressions: 0,
            reach: 0,
            profile_views: 0,
            follower_count: 0,
            saved_count: 0,
            video_views: 0
          }

          return {
            ...basePost,
            engagement: {
              likes: instagramStats.like_count || 0,
              comments: instagramStats.comments_count || 0
            },
            instagram_stats: {
              impressions: instagramStats.impressions || 0,
              reach: instagramStats.reach || 0,
              profile_views: instagramStats.profile_views || 0,
              follower_count: instagramStats.follower_count || 0,
              saved_count: instagramStats.saved_count || 0,
              video_views: instagramStats.video_views || 0
            },
            instagram_link: board.instagram_link || null
          }
        })
      )

      setPosts(transformedPosts)
    } catch (error) {
      toast({
        title: "게시글 목록 불러오기 실패",
        description: error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.",
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  // 플랫폼 번호를 이름으로 변환
  const getPlatformName = (platformNumber: number) => {
    switch (platformNumber) {
      case 0: return 'Instagram'
      case 1: return 'Blog'
      case 2: return 'Facebook'
      default: return 'Instagram'
    }
  }

  // 상태 번호를 이름으로 변환
  const getStatusName = (statusNumber: number) => {
    switch (statusNumber) {
      case 1: return 'draft' as const     // 임시저장
      case 2: return 'scheduled' as const // 예약됨
      case 3: return 'published' as const // 발행됨
      default: return 'draft' as const
    }
  }

  // 컴포넌트 마운트 시 데이터 가져오기
  useEffect(() => {
    fetchPosts()
  }, [])

  // 예약된 게시글이 있을 때 주기적으로 상태 확인 (60초마다)
  useEffect(() => {
    const hasScheduledPosts = posts.some(post => post.status === 'scheduled')

    if (hasScheduledPosts) {
      const interval = setInterval(() => {
        fetchPosts() // 예약된 게시글이 있으면 60초마다 새로고침
      }, 60000) // 60초

      return () => clearInterval(interval)
    }
  }, [posts])

  // 새 게시글 처리
  useEffect(() => {
    const newPostTitle = searchParams.get('title')
    const newPostContent = searchParams.get('content')
    const newPostModel = searchParams.get('model')
    const newPostPlatform = searchParams.get('platform')
    const newPostHashtags = searchParams.get('hashtags')

    if (newPostTitle && newPostContent && newPostModel && !hasAddedNewPost.current) {
      hasAddedNewPost.current = true

      const newPost: Post = {
        id: Date.now().toString(),
        board_id: Date.now().toString(),
        title: newPostTitle,
        board_topic: newPostTitle,
        content: newPostContent,
        board_description: newPostContent,
        author: newPostModel,
        modelName: newPostModel,
        status: "published",
        createdAt: new Date().toISOString(),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        platform: newPostPlatform || "Instagram",
        board_platform: 0,
        board_status: 1,
        influencer_id: "temp",
        user_id: "temp",
        team_id: 1,
        group_id: 1,
        board_hash_tag: newPostHashtags || "",
        image_url: "/placeholder.svg?height=400&width=400",
        engagement: { likes: 0, comments: 0 },
        hashtags: newPostHashtags ? newPostHashtags.split(' ').filter(tag => tag.trim()).map(tag => tag.startsWith('#') ? tag : `#${tag}`) : [],
        media: {
          type: "image",
          urls: ["/placeholder.svg?height=400&width=400"]
        }
      }

      setPosts(prev => [newPost, ...prev])
    }
  }, [searchParams])

  // 고유한 모델 목록 추출
  const uniqueModels = Array.from(new Set(posts.map(post => post.modelName)))
  // 고유한 플랫폼 목록 추출
  const uniquePlatforms = Array.from(new Set(posts.map(post => post.platform).filter(Boolean))) as string[]

  const filteredPosts = posts.filter((post) => {
    const matchesSearch =
      (post.title || post.board_topic || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (post.content || post.board_description || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (post.author || 'AI 인플루언서').toLowerCase().includes(searchTerm.toLowerCase())

    const matchesStatus = statusFilter === "all" || post.status === statusFilter

    const matchesModel = modelFilter === "all" || (post.modelName || 'AI 인플루언서') === modelFilter
    const matchesPlatform = platformFilter.length === 0 || platformFilter.some(p => post.platform === p)

    return matchesSearch && matchesStatus && matchesModel && matchesPlatform
  })

  const handleDeletePost = async (postId: string | undefined) => {
    if (!postId) return

    // 삭제할 게시글 정보 찾기
    const postToDelete = posts.find((post) => (post.id || post.board_id) === postId)
    const postTitle = postToDelete?.title || postToDelete?.board_topic || "게시글"

    try {
      await apiClient.delete(`/api/v1/boards/${postId}`)
      setPosts((prev) => prev.filter((post) => (post.id || post.board_id) !== postId))

      toast({
        title: "🗑️ 게시글 삭제 완료",
        description: `"${postTitle}" 게시글이 성공적으로 삭제되었습니다.`,
        variant: "default",
      })
    } catch (error) {
      toast({
        title: "❌ 게시글 삭제 실패",
        description: `"${postTitle}" 게시글 삭제 중 오류가 발생했습니다.`,
        variant: "destructive",
      })
    }
  }

  const handlePublishPost = async (postId: string | undefined) => {
    if (!postId) return

    // 발행할 게시글 정보 찾기
    const postToPublish = posts.find((post) => (post.id || post.board_id) === postId)
    const postTitle = postToPublish?.title || postToPublish?.board_topic || "게시글"
    const platform = postToPublish?.platform || "소셜미디어"

    try {
      // 1. 먼저 데이터베이스 상태 업데이트
      await apiClient.put(`/api/v1/boards/${postId}`, { board_status: 3 }) // 3 = published

      // 2. 인스타그램 플랫폼인 경우 자동 업로드 시도
      if (postToPublish?.platform === "Instagram" && postToPublish?.influencer_id) {
        try {
          // 인스타그램 업로드 가능 여부 확인
          const canUpload = await InstagramPostingService.checkInstagramPostingAvailability(postToPublish.influencer_id);

          if (canUpload) {
            // 인스타그램에 업로드
            const result = await InstagramPostingService.postToInstagram(postToPublish.influencer_id!, {
              board_id: postToPublish.board_id!,
              caption: postToPublish.content || postToPublish.board_description,
              hashtags: postToPublish.hashtags || []
            });

            if (result.success) {
              toast({
                title: "✅ 게시글 발행 및 인스타그램 업로드 완료",
                description: `"${postTitle}" 게시글이 성공적으로 발행되고 인스타그램에도 업로드되었습니다.`,
                variant: "default",
              })
            }
          } else {
            toast({
              title: "📤 게시글 발행 완료 (인스타그램 미연동)",
              description: `"${postTitle}" 게시글이 발행되었습니다. 인스타그램 업로드를 원하시면 계정을 연동해주세요.`,
              variant: "default",
            })
          }
        } catch (instagramError: any) {
          toast({
            title: "📤 게시글 발행 완료 (인스타그램 업로드 실패)",
            description: `"${postTitle}" 게시글이 발행되었지만 인스타그램 업로드에 실패했습니다: ${instagramError.message}`,
            variant: "destructive",
          })
        }
      } else {
        // 인스타그램이 아닌 경우 일반 발행
        toast({
          title: "📤 게시글 발행 완료",
          description: `"${postTitle}" 게시글이 성공적으로 발행되었습니다.`,
          variant: "default",
        })
      }

      // 3. UI 상태 업데이트
      setPosts(currentPosts =>
        currentPosts.map(p =>
          (p.id || p.board_id) === postId ? { ...p, status: 'published' as const, board_status: 3 } : p
        )
      );

    } catch (error) {
      toast({
        title: "❌ 게시글 발행 실패",
        description: `"${postTitle}" 게시글 발행 중 오류가 발생했습니다.`,
        variant: "destructive",
      })
    }
  };

  const handleInstagramUpload = async (post: Post) => {
    if (!post.influencer_id || !post.board_id) {
      toast({
        title: "❌ 업로드 실패",
        description: "인플루언서 정보가 없습니다.",
        variant: "destructive",
      })
      return;
    }

    try {
      // 인스타그램 업로드 가능 여부 확인
      const canUpload = await InstagramPostingService.checkInstagramPostingAvailability(post.influencer_id);

      if (!canUpload) {
        toast({
          title: "❌ 인스타그램 연동 필요",
          description: "먼저 인스타그램 계정을 연동해주세요.",
          variant: "destructive",
        })
        return;
      }

      // 인스타그램에 업로드
      const result = await InstagramPostingService.postToInstagram(post.influencer_id, {
        board_id: post.board_id,
        caption: post.content || post.board_description,
        hashtags: post.hashtags || []
      });

      if (result.success) {
        toast({
          title: "✅ 인스타그램 업로드 완료",
          description: result.message,
          variant: "default",
        })

        // 게시글 상태 업데이트
        setPosts(posts => posts.map(p => {
          if (p.board_id === post.board_id) {
            return {
              ...p,
              status: 'published' as const,
              publishedAt: new Date().toISOString()
            };
          }
          return p;
        }));
      }
    } catch (error: any) {
      toast({
        title: "❌ 인스타그램 업로드 실패",
        description: error.message || "인스타그램 업로드 중 오류가 발생했습니다.",
        variant: "destructive",
      })
    }
  }

  const handleApplyFilters = () => {
    setStatusFilter(tempStatusFilter)
    setModelFilter(tempModelFilter)
    setPlatformFilter(tempPlatformFilter)
    setIsFilterModalOpen(false)
  }

  const handleOpenFilterModal = () => {
    setTempStatusFilter(statusFilter)
    setTempModelFilter(modelFilter)
    setTempPlatformFilter(platformFilter)
    setIsFilterModalOpen(true)
  }

  const handleViewPost = (post: Post) => {
    setSelectedPost(post)
    setIsViewModalOpen(true)
  }



  const formatDate = (dateString: string | undefined) => {
    if (!dateString) return ""
    return convertUTCToKST(dateString)
  }

  const formatFullDate = (dateString: string | undefined) => {
    if (!dateString) return ""
    return formatDateKorean(dateString)
  }

  const formatRelativeTime = (dateString: string | undefined) => {
    if (!dateString) return ""
    return getRelativeTime(dateString)
  }

  useEffect(() => {
    if (isViewModalOpen && selectedPost) {
      setEditMode(false);
      setEditTitle(selectedPost.title || selectedPost.board_topic || "");
      setEditContent(selectedPost.content || selectedPost.board_description || "");
      setEditHashtags(selectedPost.hashtags ? selectedPost.hashtags.join(" ") : "");

      // 예약 날짜 설정
      const formattedDate = selectedPost.scheduledAt ? selectedPost.scheduledAt.slice(0, 16) : "";
      setEditScheduledAt(formattedDate);
    }
  }, [isViewModalOpen, selectedPost]);

  const handleEditSave = async () => {
    if (!selectedPost || isSaving) return;

    const originalTitle = selectedPost.title || selectedPost.board_topic || "게시글"
    const hasChanges = editTitle !== originalTitle ||
      editContent !== (selectedPost.content || selectedPost.board_description) ||
      editHashtags !== (selectedPost.hashtags?.join(" ") || "") ||
      editScheduledAt !== (selectedPost.scheduledAt ? selectedPost.scheduledAt.slice(0, 16) : "")

    if (!hasChanges) {
      toast({
        title: "ℹ️ 변경사항 없음",
        description: "수정할 내용이 없습니다.",
        variant: "default",
      })
      setEditMode(false)
      return
    }

    setIsSaving(true);
    try {
      // 백엔드 API 호출하여 게시글 수정
      const boardId = selectedPost.board_id || selectedPost.id;
      const updateData = {
        board_topic: editTitle,
        board_description: editContent,
        board_hash_tag: editHashtags,
        ...(editScheduledAt && { reservation_at: `${editScheduledAt}:00` })
      };

      const response = await apiClient.put(`/api/v1/boards/${boardId}`, updateData);

      // apiClient는 성공 시 데이터를 직접 반환하고, 실패 시 예외를 던집니다
      // 따라서 여기까지 왔다면 성공한 것입니다

      // 성공 시 프론트엔드 상태 업데이트
      setPosts(posts => {
        const newPosts = posts.map(post => {
          if (post.id !== selectedPost.id) return post;

          // 게시글 수정 시에는 상태를 변경하지 않고 원래 상태 유지
          return {
            ...post,
            title: editTitle,
            content: editContent,
            hashtags: editHashtags.split(" ").filter(tag => tag.startsWith("#")),
            // 상태는 원래대로 유지
            status: post.status,
            scheduledAt: post.scheduledAt,
          };
        });
        // 최신 selectedPost로 갱신
        const updated = newPosts.find(p => p.id === selectedPost.id);
        if (updated) setSelectedPost(updated);
        return newPosts;
      });
      setEditMode(false);
      setIsViewModalOpen(false); // 모달 닫기

      toast({
        title: "✏️ 게시글 수정 완료",
        description: `"${editTitle}" 게시글이 성공적으로 수정되었습니다.`,
        variant: "default",
      })
    } catch (error) {
      toast({
        title: "❌ 게시글 수정 실패",
        description: `"${editTitle}" 게시글 수정 중 오류가 발생했습니다.`,
        variant: "destructive",
      })
    } finally {
      setIsSaving(false);
    }
  };



  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <div className="flex justify-between items-center mb-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">게시글 관리</h1>
              <p className="text-gray-600 mt-2">AI 인플루언서가 생성한 게시글을 관리하세요</p>
            </div>
          </div>



          <div className="flex items-center gap-2 mb-6">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
              <Input
                placeholder="게시글 검색..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <Dialog open={isFilterModalOpen} onOpenChange={setIsFilterModalOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" className="flex items-center gap-2" onClick={handleOpenFilterModal}>
                  <Filter className="h-4 w-4" />
                  필터
                  {(modelFilter !== "all" || platformFilter.length > 0) && (
                    <Badge variant="secondary" className="ml-1">
                      {[modelFilter !== "all" ? 1 : 0, platformFilter.length].reduce((a, b) => a + b, 0)}
                    </Badge>
                  )}
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-md">
                <DialogHeader>
                  <DialogTitle>필터 설정</DialogTitle>
                </DialogHeader>
                <div className="space-y-6">
                  {/* 모델 필터 */}
                  <div>
                    <h3 className="font-medium text-sm text-gray-900 mb-3">모델</h3>
                    <div className="grid grid-cols-1 gap-2">
                      <button
                        onClick={() => setTempModelFilter("all")}
                        className={`text-left px-3 py-2 rounded-md text-sm transition-colors ${tempModelFilter === "all"
                          ? "bg-blue-100 text-blue-700 border border-blue-200"
                          : "bg-gray-50 text-gray-700 hover:bg-gray-100 border border-gray-200"
                          }`}
                      >
                        전체 모델
                      </button>
                      {uniqueModels.map((model) => (
                        <button
                          key={model}
                          onClick={() => setTempModelFilter(model || "")}
                          className={`text-left px-3 py-2 rounded-md text-sm transition-colors ${tempModelFilter === model
                            ? "bg-blue-100 text-blue-700 border border-blue-200"
                            : "bg-gray-50 text-gray-700 hover:bg-gray-100 border border-gray-200"
                            }`}
                        >
                          {model}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* 플랫폼 필터 */}
                  <div>
                    <h3 className="font-medium text-sm text-gray-900 mb-3">플랫폼</h3>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        onClick={() => setTempPlatformFilter([])}
                        className={`text-left px-3 py-2 rounded-md text-sm transition-colors ${tempPlatformFilter.length === 0
                          ? "bg-blue-100 text-blue-700 border border-blue-200"
                          : "bg-gray-50 text-gray-700 hover:bg-gray-100 border border-gray-200"
                          }`}
                      >
                        전체 플랫폼
                      </button>
                      {uniquePlatforms.map((platform) => (
                        <button
                          key={platform}
                          onClick={() => {
                            if (tempPlatformFilter.includes(platform || "")) {
                              setTempPlatformFilter(tempPlatformFilter.filter(p => p !== platform))
                            } else {
                              setTempPlatformFilter([...tempPlatformFilter, platform || ""])
                            }
                          }}
                          className={`text-left px-3 py-2 rounded-md text-sm transition-colors flex items-center gap-2 ${tempPlatformFilter.includes(platform || "")
                            ? "bg-purple-100 text-purple-700 border border-purple-200"
                            : "bg-gray-50 text-gray-700 hover:bg-gray-100 border border-gray-200"
                            }`}
                        >
                          {platform}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
                {/* 적용하기 버튼 */}
                <div className="flex justify-end gap-2 pt-4 border-t">
                  <Button
                    variant="outline"
                    onClick={() => setIsFilterModalOpen(false)}
                  >
                    취소
                  </Button>
                  <Button
                    onClick={handleApplyFilters}
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    적용하기
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
            <div className="flex-1 flex justify-end">
              <Link href="/create-post">
                <Button className="flex items-center space-x-2 text-white bg-blue-600 hover:bg-blue-700">
                  <Plus className="h-4 w-4" />
                  <span>새 게시글 작성</span>
                </Button>
              </Link>
            </div>
          </div>

          {(modelFilter !== "all" || platformFilter.length > 0) && (
            <div className="flex items-center gap-2 mb-4 flex-wrap">
              <span className="text-sm text-gray-500">활성 필터:</span>
              {modelFilter !== "all" && (
                <Badge variant="outline" className="text-xs flex items-center gap-1">
                  모델: {modelFilter}
                  <button
                    onClick={() => setModelFilter("all")}
                    className="ml-1 hover:text-red-600 transition-colors"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              )}
              {platformFilter.map((platform) => (
                <Badge key={platform} variant="outline" className="text-xs flex items-center gap-1">
                  플랫폼: {platform}
                  <button
                    onClick={() => setPlatformFilter(platformFilter.filter(p => p !== platform))}
                    className="ml-1 hover:text-red-600 transition-colors"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setStatusFilter("all");
                  setModelFilter("all");
                  setPlatformFilter([]);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                모든 필터 초기화
              </Button>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <Card
              className={`cursor-pointer transition-shadow ${statusFilter === "all" ? "ring-2 ring-blue-400" : "hover:shadow-lg"}`}
              onClick={() => setStatusFilter("all")}
            >
              <CardContent className="p-6">
                <div className="text-center">
                  <p className="text-3xl font-bold text-blue-600">{posts.length}</p>
                  <p className="text-sm text-gray-600 mt-1">전체</p>
                </div>
              </CardContent>
            </Card>
            <Card
              className={`cursor-pointer transition-shadow ${statusFilter === "published" ? "ring-2 ring-green-400" : "hover:shadow-lg"}`}
              onClick={() => setStatusFilter("published")}
            >
              <CardContent className="p-6">
                <div className="text-center">
                  <p className="text-3xl font-bold text-green-600">{posts.filter((p) => p.status === "published").length}</p>
                  <p className="text-sm text-gray-600 mt-1">발행됨</p>
                </div>
              </CardContent>
            </Card>
            <Card
              className={`cursor-pointer transition-shadow ${statusFilter === "scheduled" ? "ring-2 ring-blue-400" : "hover:shadow-lg"}`}
              onClick={() => setStatusFilter("scheduled")}
            >
              <CardContent className="p-6">
                <div className="text-center">
                  <p className="text-3xl font-bold text-blue-600">{posts.filter((p) => p.status === "scheduled").length}</p>
                  <p className="text-sm text-gray-600 mt-1">예약됨</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <p className="text-gray-500 text-lg">게시글을 불러오는 중...</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {filteredPosts.map((post) => (
              <PostCard
                key={post.id}
                post={post}
                onView={handleViewPost}
                onDelete={handleDeletePost}
                onPublish={handlePublishPost}
                onInstagramUpload={handleInstagramUpload}
                showActions={true}
                showInfluencerInfo={false}
                variant="list"
              />
            ))}
          </div>
        )}

        {!loading && filteredPosts.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500 text-lg">검색 결과가 없습니다.</p>
            <p className="text-gray-400 mt-2">다른 검색어를 시도해보세요.</p>
          </div>
        )}

        {/* 게시글 상세 보기 모달 */}
        <Dialog open={isViewModalOpen} onOpenChange={setIsViewModalOpen}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center space-x-2">
                <Eye className="h-5 w-5" />
                <span>게시글 상세 보기</span>
              </DialogTitle>
            </DialogHeader>

            {selectedPost && (
              <div className="space-y-6">
                {/* 게시글 기본 정보 */}
                <div className="flex items-center space-x-3 pb-4 border-b">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      {editMode ? (
                        <Input
                          value={editTitle}
                          onChange={e => setEditTitle(e.target.value)}
                          className="font-semibold text-gray-900 text-lg"
                        />
                      ) : (
                        <h3 className="font-semibold text-gray-900">{selectedPost.title || selectedPost.board_topic}</h3>
                      )}
                      <Badge className={
                        selectedPost.status === "published" ? "bg-green-100 text-green-800" :
                          selectedPost.status === "scheduled" ? "bg-blue-100 text-blue-800" :
                            "bg-gray-100 text-gray-800"
                      }>
                        {selectedPost.status === "published" ? "발행됨" :
                          selectedPost.status === "scheduled" ? "예약됨" : "임시저장"}
                      </Badge>
                      {selectedPost.platform && (
                        <Badge className={
                          selectedPost.platform === "Instagram" ? "bg-pink-100 text-pink-800" :
                            selectedPost.platform === "Blog" ? "bg-orange-100 text-orange-800" :
                              selectedPost.platform === "Facebook" ? "bg-blue-100 text-blue-800" :
                                "bg-gray-100 text-gray-800"
                        }>
                          {selectedPost.platform}
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center space-x-2 text-sm text-gray-500 mt-1">
                      <User className="h-4 w-4" />
                      <span>{selectedPost.author || 'AI 인플루언서'}</span>
                      <span>•</span>
                      <Calendar className="h-4 w-4" />
                      <span>{formatFullDate(selectedPost.createdAt || selectedPost.created_at || "")}</span>
                    </div>
                  </div>
                </div>

                {/* 게시글 내용 */}
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-gray-900">게시글 내용</h4>
                  <div className="bg-gray-50 border rounded-lg p-4">
                    {editMode ? (
                      <textarea
                        value={editContent}
                        onChange={e => setEditContent(e.target.value)}
                        className="w-full h-32 p-2 border rounded"
                      />
                    ) : (
                      <div className="whitespace-pre-wrap text-gray-800 leading-relaxed">
                        {selectedPost.content || selectedPost.board_description}
                      </div>
                    )}
                  </div>
                </div>

                {/* 해시태그 */}
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-gray-900">해시태그</h4>
                  {editMode ? (
                    <Input
                      value={editHashtags}
                      onChange={e => setEditHashtags(e.target.value)}
                      placeholder="#태그1 #태그2"
                    />
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {(selectedPost.hashtags || []).map((tag, index) => (
                        <span key={index} className="text-sm text-blue-600 bg-blue-50 px-3 py-1 rounded-full">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* 예약 날짜 */}
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-gray-900">예약 날짜</h4>
                  {editMode ? (
                    <input
                      type="datetime-local"
                      value={editScheduledAt}
                      onChange={e => setEditScheduledAt(e.target.value)}
                      className="w-full p-2 border rounded"
                      placeholder="예약 날짜 선택"
                    />
                  ) : (
                    <div className="text-gray-800">
                      {selectedPost.scheduledAt ? formatFullDate(selectedPost.scheduledAt) : "예약되지 않음"}
                    </div>
                  )}
                </div>

                {/* 미디어 정보 */}
                {selectedPost.media && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-gray-900">미디어</h4>
                    <div className="bg-gray-50 border rounded-lg p-4">
                      <div className="flex items-center space-x-2 mb-2">
                        <span className="text-sm font-medium text-gray-700">
                          {selectedPost.media.type === "image" && "이미지"}
                          {selectedPost.media.type === "video" && "비디오"}
                          {selectedPost.media.type === "carousel" && "캐러셀"}
                        </span>
                        {selectedPost.media.type === "carousel" && (
                          <Badge variant="outline" className="text-xs">
                            {selectedPost.media.urls.length}개 파일
                          </Badge>
                        )}
                      </div>
                      {selectedPost.media.thumbnailUrl && (
                        <div className="mt-2">
                          <img
                            src={selectedPost.media.thumbnailUrl}
                            alt="미디어 썸네일"
                            className="w-32 h-32 object-cover rounded-lg border"
                          />
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 성과 지표 */}
                {selectedPost.status === "published" && selectedPost.engagement && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-gray-900">성과 지표</h4>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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


                        {/* Instagram 인사이트 추가 */}
                        {selectedPost.platform === 'Instagram' && selectedPost.instagram_stats && (
                          <>
                            {selectedPost.instagram_stats.reach > 0 && (
                              <div className="text-center">
                                <div className="flex items-center justify-center space-x-2 mb-1">
                                  <Users className="h-5 w-5 text-orange-500" />
                                  <span className="text-lg font-bold text-gray-900">
                                    {selectedPost.instagram_stats.reach.toLocaleString()}
                                  </span>
                                </div>
                                <p className="text-sm text-gray-600">도달</p>
                              </div>
                            )}
                            {selectedPost.instagram_stats.impressions > 0 && (
                              <div className="text-center">
                                <div className="flex items-center justify-center space-x-2 mb-1">
                                  <BarChart3 className="h-5 w-5 text-teal-500" />
                                  <span className="text-lg font-bold text-gray-900">
                                    {selectedPost.instagram_stats.impressions.toLocaleString()}
                                  </span>
                                </div>
                                <p className="text-sm text-gray-600">노출</p>
                              </div>
                            )}
                            {selectedPost.instagram_stats.saved_count > 0 && (
                              <div className="text-center">
                                <div className="flex items-center justify-center space-x-2 mb-1">
                                  <Bookmark className="h-5 w-5 text-yellow-500" />
                                  <span className="text-lg font-bold text-gray-900">
                                    {selectedPost.instagram_stats.saved_count.toLocaleString()}
                                  </span>
                                </div>
                                <p className="text-sm text-gray-600">저장</p>
                              </div>
                            )}
                          </>
                        )}
                      </div>


                    </div>
                  </div>
                )}



                {/* 액션 버튼 */}
                <div className="flex justify-end space-x-2 pt-4 border-t">
                  {selectedPost.status !== "published" && (
                    editMode ? (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleEditSave}
                          disabled={isSaving}
                        >
                          {isSaving ? "저장 중..." : "저장"}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setEditMode(false)}>
                          취소
                        </Button>
                      </>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setEditMode(true)}
                      >
                        <Edit className="h-4 w-4 mr-2" />
                        수정
                      </Button>
                    )
                  )}
                  {selectedPost.status === "published" && selectedPost.instagram_link && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        // 백엔드에서 제공하는 인스타그램 링크로 이동
                        if (selectedPost.instagram_link) {
                          window.open(selectedPost.instagram_link, '_blank');
                        }
                      }}
                      className="flex items-center space-x-2"
                    >
                      <ExternalLink className="h-4 w-4" />
                      <span>게시글 링크로 이동</span>
                    </Button>
                  )}
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}

export default function PostListPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <PostListContent />
    </Suspense>
  )
} 