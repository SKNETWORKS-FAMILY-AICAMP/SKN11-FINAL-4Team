import { RefreshCw, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { Post } from "@/components/ui/post-card";

interface ContentTabProps {
  posts: Post[];
  isPostsLoading: boolean;
  loadPostsData: () => void;
  handleViewPostDetail: (post: Post) => void;
  PostCard: React.ComponentType<{
    post: Post;
    onView?: (post: Post) => void;
    showActions?: boolean;
    showInfluencerInfo?: boolean;
    variant?: "list" | "content";
  }>;
}

export default function ContentTab({
  posts,
  isPostsLoading,
  loadPostsData,
  handleViewPostDetail,
  PostCard
}: ContentTabProps) {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            최근 게시된 콘텐츠
          </h3>
          <p className="text-sm text-gray-600">
            이 AI 모델이 생성한 게시글 목록입니다
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={loadPostsData}
          disabled={isPostsLoading}
          className="flex items-center space-x-2"
        >
          <RefreshCw
            className={`h-4 w-4 ${isPostsLoading ? "animate-spin" : ""}`}
          />
          <span>새로고침</span>
        </Button>
      </div>

      {isPostsLoading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-500 text-lg">
            게시글을 불러오는 중...
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {posts.map((post) => (
              <PostCard
                key={post.id}
                post={post}
                onView={handleViewPostDetail}
                showActions={false}
                showInfluencerInfo={false}
                variant="content"
              />
            ))}
          </div>

          {posts.length === 0 && (
            <div className="text-center py-12">
              <FileText className="h-12 w-12 mx-auto mb-4 text-gray-300" />
              <p className="text-gray-500 text-lg">
                아직 생성된 콘텐츠가 없습니다
              </p>
              <p className="text-gray-400 mt-2">
                첫 번째 게시글을 작성해보세요!
              </p>
              <Link href="/create-post">
                <Button className="mt-4">
                  <FileText className="h-4 w-4 mr-2" />
                  게시글 작성하기
                </Button>
              </Link>
            </div>
          )}
        </>
      )}
    </div>
  );
}