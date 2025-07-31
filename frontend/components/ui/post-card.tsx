"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Calendar, User, Heart, MessageCircle, Users, BarChart3, UploadCloud, Instagram, Trash2, Bookmark } from "lucide-react"
import { convertUTCToKST, formatDateKorean } from "@/lib/utils/timezone"
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


// 게시글 타입 정의
export interface Post {
  board_id?: string
  id?: string
  board_topic?: string
  title?: string
  board_description?: string
  content?: string
  influencer_id?: string
  user_id?: string
  team_id?: number
  group_id?: number
  board_platform?: number
  platform?: string
  board_hash_tag?: string
  hashtags?: string[]
  board_status?: number
  status?: "draft" | "published" | "scheduled"
  image_url?: string
  created_at?: string
  updated_at?: string
  createdAt?: string
  author?: string
  modelName?: string
  publishedAt?: string
  scheduledAt?: string
  engagement?: {
    likes: number
    comments: number
  }
  media?: {
    type: "image" | "video" | "carousel"
    urls: string[]
    thumbnailUrl?: string
  }
  // 인스타그램 통계 추가
  instagram_stats?: {
    impressions?: number
    reach?: number
    profile_views?: number
    follower_count?: number
    saved_count?: number
    video_views?: number
  }
  // Instagram 링크 추가
  instagram_link?: string
  influencerName?: string
  influencerDescription?: string
  influencer_image_url?: string  // 인플루언서 프로필 이미지 URL 추가
}

interface PostCardProps {
  post: Post
  onView?: (post: Post) => void
  onDelete?: (postId: string) => void
  onPublish?: (postId: string) => void
  onInstagramUpload?: (post: Post) => void
  showActions?: boolean
  showInfluencerInfo?: boolean
  variant?: "list" | "content"
}

export function PostCard({
  post,
  onView,
  onDelete,
  onPublish,
  onInstagramUpload,
  showActions = true,
  showInfluencerInfo = false,
  variant = "list"
}: PostCardProps) {

  // 상태 배지 생성
  const getStatusBadge = (status: Post["status"]) => {
    switch (status) {
      case "published":
        return <Badge className="bg-green-100 text-green-800 whitespace-nowrap">발행됨</Badge>
      case "scheduled":
        return <Badge className="bg-blue-100 text-blue-800 whitespace-nowrap">예약됨</Badge>
      case "draft":
        return <Badge className="bg-gray-100 text-gray-800 whitespace-nowrap">임시저장</Badge>
      default:
        return <Badge className="bg-gray-100 text-gray-800 whitespace-nowrap">임시저장</Badge>
    }
  }

  // 플랫폼 배지 생성
  const getPlatformBadge = (platform: string | undefined) => {
    if (!platform) return null

    const platformColors = {
      'Instagram': 'bg-pink-100 text-pink-800',
      'Blog': 'bg-orange-100 text-orange-800',
      'Facebook': 'bg-blue-100 text-blue-800'
    }

    const colorClass = platformColors[platform as keyof typeof platformColors] || 'bg-gray-100 text-gray-800'

    return <Badge className={`${colorClass} whitespace-nowrap`}>{platform}</Badge>
  }

  // 날짜 포맷팅
  const formatDate = (dateString: string | undefined) => {
    if (!dateString) return ""
    return convertUTCToKST(dateString)
  }

  // 해시태그 렌더링
  const renderHashtags = () => {
    const hashtags = post.hashtags || []
    const boardHashtags = post.board_hash_tag ?
      post.board_hash_tag.split(' ').filter(tag => tag.trim()).map(tag => tag.startsWith('#') ? tag : `#${tag}`) :
      []

    const allHashtags = hashtags.length > 0 ? hashtags : boardHashtags

    // variant에 따라 표시 개수 제한
    const maxDisplayCount = variant === "content" ? 3 : 5
    const displayHashtags = allHashtags.slice(0, maxDisplayCount)

    return (
      <div className="flex flex-wrap gap-1 mb-3">
        {displayHashtags.map((tag, index) => (
          <span key={index} className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded">
            {tag}
          </span>
        ))}
        {allHashtags.length > maxDisplayCount && (
          <span className="text-xs text-gray-500 px-2 py-1">
            +{allHashtags.length - maxDisplayCount}개 더
          </span>
        )}
      </div>
    )
  }

  // 인플루언서 정보 렌더링
  const renderInfluencerInfo = () => {
    if (!showInfluencerInfo) return null

    return (
      <div className="flex items-center space-x-2 mb-2">
        <div className="w-6 h-6 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center">
          <span className="text-white text-xs font-medium">AI</span>
        </div>
        <span className="text-sm font-medium text-gray-700">
          {post.influencerName || 'AI 인플루언서'}
        </span>
        {post.influencerDescription && (
          <span className="text-xs text-gray-500">
            • {post.influencerDescription}
          </span>
        )}
      </div>
    )
  }

  // 성과지표 렌더링
  const renderEngagement = () => {
    if (post.status !== "published" || !post.engagement) return null

    return (
      <div className="flex items-center space-x-4 text-sm text-gray-600">
        <div className="flex items-center space-x-1">
          <Heart className="h-4 w-4 text-red-500" />
          <span>{post.engagement.likes.toLocaleString()}</span>
        </div>
        <div className="flex items-center space-x-1">
          <MessageCircle className="h-4 w-4 text-blue-500" />
          <span>{post.engagement.comments.toLocaleString()}</span>
        </div>
        {/* 인스타그램 추가 통계 표시 */}
        {post.platform === 'Instagram' && post.instagram_stats && (
          <>
            {typeof post.instagram_stats.reach === 'number' && post.instagram_stats.reach > 0 && (
              <div className="flex items-center space-x-1">
                <Users className="h-4 w-4 text-orange-500" />
                <span>{post.instagram_stats.reach.toLocaleString()}</span>
              </div>
            )}
            {typeof post.instagram_stats.impressions === 'number' && post.instagram_stats.impressions > 0 && (
              <div className="flex items-center space-x-1">
                <BarChart3 className="h-4 w-4 text-teal-500" />
                <span>{post.instagram_stats.impressions.toLocaleString()}</span>
              </div>
            )}
            {typeof post.instagram_stats.saved_count === 'number' && post.instagram_stats.saved_count > 0 && (
              <div className="flex items-center space-x-1">
                <Bookmark className="h-4 w-4 text-yellow-500" />
                <span>{post.instagram_stats.saved_count.toLocaleString()}</span>
              </div>
            )}
            {typeof post.instagram_stats.video_views === 'number' && post.instagram_stats.video_views > 0 && (
              <div className="flex items-center space-x-1">
                <BarChart3 className="h-4 w-4 text-purple-500" />
                <span>{post.instagram_stats.video_views.toLocaleString()}</span>
              </div>
            )}
          </>
        )}
      </div>
    )
  }

  // 액션 버튼 렌더링
  const renderActions = () => {
    if (!showActions) return null

    return (
      <div className="flex items-center space-x-2" onClick={e => e.stopPropagation()}>
        {onDelete && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button size="icon" variant="ghost" title="삭제">
                <Trash2 className="h-4 w-4 text-red-500" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>게시글 삭제</AlertDialogTitle>
                <AlertDialogDescription>
                  정말 이 게시글을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>취소</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => onDelete(post.id || post.board_id || "")}
                  className="bg-red-600 hover:bg-red-700"
                >
                  삭제
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </div>
    )
  }

  return (
    <Card
      className={`hover:shadow-md transition-shadow ${variant === "content" ? "cursor-default" : "cursor-pointer group"}`}
      onClick={variant === "content" ? undefined : () => onView?.(post)}
    >
      <CardContent className="p-6 flex flex-col h-full">
        {/* 상태와 플랫폼 배지를 오른쪽 상단에 고정 */}
        <div className="flex justify-between items-start mb-4 flex-1">
          <div className="flex-1">
            <h4 className="text-lg font-semibold text-gray-900 mb-2">
              {post.title || post.board_topic}
            </h4>



            <p className="text-gray-600 text-sm line-clamp-3 mb-3">
              {(post.content || post.board_description || '').length > 150
                ? `${(post.content || post.board_description || '').substring(0, 150)}...`
                : (post.content || post.board_description || '')}
            </p>

            {renderHashtags()}
          </div>

          {/* 오른쪽 상단에 배지들 배치 */}
          <div className="flex flex-col items-end space-y-2 ml-4">
            {getPlatformBadge(post.platform || "")}
            {getStatusBadge(post.status)}
          </div>
        </div>

        {/* 하단 정보 - 항상 하단에 고정 */}
        <div className="mt-auto pt-4 border-t">
          {variant === "content" ? (
            <div className="flex items-center justify-between text-sm text-gray-500">
              <div className="flex items-center space-x-1">
                <User className="h-4 w-4" />
                <span>{post.influencerName || post.author || 'AI 인플루언서'}</span>
              </div>
              <div className="flex items-center space-x-1">
                <Calendar className="h-4 w-4" />
                {post.status === 'scheduled' && post.scheduledAt ? (
                  <span>예약 발행: {formatDate(post.scheduledAt)}</span>
                ) : post.status === 'published' && post.publishedAt ? (
                  <span>발행: {formatDate(post.publishedAt)}</span>
                ) : (
                  <span>생성: {formatDate(post.createdAt || post.created_at || "")}</span>
                )}
              </div>
            </div>
          ) : (
            <div className="flex justify-between items-center">
              <div className="flex items-center space-x-4 text-sm text-gray-500">
                <div className="flex items-center space-x-1">
                  <User className="h-4 w-4" />
                  <span>{post.influencerName || post.author || ''}</span>
                </div>
              </div>
              <div className="flex items-center space-x-1 text-sm text-gray-500">
                <Calendar className="h-4 w-4" />
                {post.status === 'scheduled' && post.scheduledAt ? (
                  <span>예약 발행: {formatDate(post.scheduledAt)}</span>
                ) : post.status === 'published' && post.publishedAt ? (
                  <span>발행: {formatDate(post.publishedAt)}</span>
                ) : (
                  <span>생성: {formatDate(post.createdAt || post.created_at || "")}</span>
                )}
              </div>
            </div>
          )}

          {/* 성과지표와 액션 버튼들 - content variant가 아닐 때만 표시 */}
          {variant !== "content" && (
            <div className="flex items-center justify-between pt-3 mt-3">
              <div className="flex-1">
                {renderEngagement()}
              </div>
              <div className="flex items-center">
                {renderActions()}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
} 