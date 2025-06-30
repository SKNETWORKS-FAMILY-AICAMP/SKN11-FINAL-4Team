"use client"

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Heart, MessageCircle, Eye, Users, TrendingUp } from 'lucide-react'

interface InstagramUser {
  id: string;
  username: string;
  account_type: 'BUSINESS' | 'CREATOR' | 'PERSONAL';
  media_count: number;
  name?: string;
  biography?: string;
  website?: string;
  profile_picture_url?: string;
  followers_count?: number;
  follows_count?: number;
}

interface InstagramMedia {
  id: string;
  caption?: string;
  media_type: 'IMAGE' | 'VIDEO' | 'CAROUSEL_ALBUM';
  media_url: string;
  permalink: string;
  timestamp: string;
  like_count?: number;
  comments_count?: number;
  thumbnail_url?: string;
}

interface InstagramInsights {
  name: string;
  period: string;
  values: Array<{
    value: number;
    end_time: string;
  }>;
  title: string;
  description: string;
}

interface Props {
  accessToken: string;
  userData: any;
}

export default function InstagramDashboard({ accessToken, userData }: Props) {
  const [userInfo, setUserInfo] = useState<InstagramUser | null>(null)
  const [media, setMedia] = useState<InstagramMedia[]>([])
  const [insights, setInsights] = useState<InstagramInsights[]>([])
  const [loading, setLoading] = useState(false)

  const loadUserData = async () => {
    setLoading(true)
    try {
      // 사용자 정보 로드
      const userResponse = await fetch(`/api/instagram/accounts?access_token=${accessToken}`)
      const userData = await userResponse.json()
      
      if (userData.success) {
        setUserInfo(userData.data)
        
        // 미디어 로드
        const mediaResponse = await fetch(`/api/instagram/media?access_token=${accessToken}&account_id=me&limit=20`)
        const mediaData = await mediaResponse.json()
        if (mediaData.success) {
          setMedia(mediaData.data)
        }
        
        // 인사이트 로드 (Business/Creator 계정만)
        if (userData.data.account_type === 'BUSINESS' || userData.data.account_type === 'CREATOR') {
          const insightsResponse = await fetch(`/api/instagram/insights?access_token=${accessToken}&account_id=me`)
          const insightsData = await insightsResponse.json()
          if (insightsData.success) {
            setInsights(insightsData.data)
          }
        }
      }
    } catch (error) {
      console.error('Failed to load user data:', error)
    } finally {
      setLoading(false)
    }
  }

  // 컴포넌트 마운트 시 데이터 로드
  React.useEffect(() => {
    if (accessToken) {
      loadUserData()
    }
  }, [accessToken])

  const formatNumber = (num: number) => {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M'
    } else if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K'
    }
    return num.toString()
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  }

  return (
    <div className="space-y-6">
      {/* 로딩 상태 */}
      {loading && (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-gray-600">계정 정보를 불러오는 중...</span>
        </div>
      )}

      {/* Instagram 사용자 정보 */}
      {userInfo && (
        <div className="space-y-6">
          {/* 계정 프로필 */}
          <Card>
            <CardContent className="p-6">
              <div className="flex items-start space-x-4">
                <Avatar className="w-20 h-20">
                  <AvatarImage src={userInfo.profile_picture_url} alt={userInfo.username} />
                  <AvatarFallback>{userInfo.username.charAt(0).toUpperCase()}</AvatarFallback>
                </Avatar>
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-2">
                    <h2 className="text-2xl font-bold">{userInfo.name || userInfo.username}</h2>
                    <Badge variant="secondary">@{userInfo.username}</Badge>
                    <Badge variant={userInfo.account_type === 'BUSINESS' ? 'default' : userInfo.account_type === 'CREATOR' ? 'secondary' : 'outline'}>
                      {userInfo.account_type}
                    </Badge>
                  </div>
                  {userInfo.biography && (
                    <p className="text-gray-600 mb-3">{userInfo.biography}</p>
                  )}
                  {userInfo.website && (
                    <a href={userInfo.website} target="_blank" rel="noopener noreferrer" 
                       className="text-blue-600 hover:underline text-sm">
                      {userInfo.website}
                    </a>
                  )}
                  <div className="flex space-x-6 mt-4">
                    {userInfo.followers_count !== undefined && (
                      <div className="text-center">
                        <div className="text-2xl font-bold text-blue-600">{formatNumber(userInfo.followers_count)}</div>
                        <div className="text-sm text-gray-500">팔로워</div>
                      </div>
                    )}
                    {userInfo.follows_count !== undefined && (
                      <div className="text-center">
                        <div className="text-2xl font-bold text-purple-600">{formatNumber(userInfo.follows_count)}</div>
                        <div className="text-sm text-gray-500">팔로잉</div>
                      </div>
                    )}
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-600">{userInfo.media_count}</div>
                      <div className="text-sm text-gray-500">게시물</div>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 탭 컨텐츠 */}
          <Tabs defaultValue="media" className="space-y-4">
            <TabsList>
              <TabsTrigger value="media">미디어</TabsTrigger>
              <TabsTrigger value="insights">인사이트</TabsTrigger>
              <TabsTrigger value="management">관리</TabsTrigger>
            </TabsList>

            {/* 미디어 탭 */}
            <TabsContent value="media" className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {media.map((item) => (
                  <Card key={item.id} className="overflow-hidden">
                    <div className="aspect-square relative">
                      <img 
                        src={item.thumbnail_url || item.media_url} 
                        alt={item.caption || 'Instagram media'}
                        className="w-full h-full object-cover"
                      />
                      <div className="absolute top-2 right-2">
                        <Badge variant={item.media_type === 'VIDEO' ? 'destructive' : 'secondary'}>
                          {item.media_type}
                        </Badge>
                      </div>
                    </div>
                    <CardContent className="p-3">
                      <p className="text-sm text-gray-600 line-clamp-2 mb-2">
                        {item.caption?.substring(0, 100)}...
                      </p>
                      <div className="flex justify-between text-sm text-gray-500">
                        <div className="flex items-center space-x-1">
                          <Heart className="w-4 h-4" />
                          <span>{item.like_count || 0}</span>
                        </div>
                        <div className="flex items-center space-x-1">
                          <MessageCircle className="w-4 h-4" />
                          <span>{item.comments_count || 0}</span>
                        </div>
                      </div>
                      <div className="text-xs text-gray-400 mt-2">
                        {formatDate(item.timestamp)}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>

            {/* 인사이트 탭 */}
            <TabsContent value="insights" className="space-y-4">
              {userInfo.account_type === 'PERSONAL' ? (
                <Card>
                  <CardContent className="p-6 text-center">
                    <div className="text-gray-500">
                      <TrendingUp className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                      <h3 className="text-lg font-medium mb-2">인사이트를 사용할 수 없습니다</h3>
                      <p className="text-sm">인사이트 기능은 비즈니스 또는 크리에이터 계정에서만 사용할 수 있습니다.</p>
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {insights.length > 0 ? insights.map((insight, index) => (
                    <Card key={index}>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">{insight.title}</CardTitle>
                        <CardDescription className="text-xs">{insight.description}</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="text-2xl font-bold text-blue-600 mb-1">
                          {insight.values[0]?.value || 0}
                        </div>
                        <div className="flex items-center text-xs text-gray-500">
                          <TrendingUp className="w-3 h-3 mr-1" />
                          {insight.period}
                        </div>
                      </CardContent>
                    </Card>
                  )) : (
                    <Card className="col-span-full">
                      <CardContent className="p-6 text-center">
                        <div className="text-gray-500">
                          <TrendingUp className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                          <p className="text-sm">인사이트 데이터를 불러오는 중이거나 데이터가 없습니다.</p>
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </div>
              )}
            </TabsContent>

            {/* 관리 탭 */}
            <TabsContent value="management" className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle>콘텐츠 관리</CardTitle>
                    <CardDescription>게시물 업로드 및 관리</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <Button className="w-full">새 게시물 업로드</Button>
                    <Button variant="outline" className="w-full">예약 게시</Button>
                    <Button variant="outline" className="w-full">스토리 관리</Button>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>소통 관리</CardTitle>
                    <CardDescription>댓글 및 메시지 관리</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <Button className="w-full">댓글 관리</Button>
                    <Button variant="outline" className="w-full">자동 응답 설정</Button>
                    <Button variant="outline" className="w-full">멘션 알림</Button>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  )
}