"use client"

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Heart, MessageCircle, Users, TrendingUp } from 'lucide-react'
import { InstagramService } from '@/lib/services/instagram.service'

interface InstagramMedia {
  id: string
  media_type: string
  media_url: string
  thumbnail_url?: string
  caption?: string
  like_count?: number
  comments_count?: number
  timestamp: string
}

interface InstagramInsights {
  title: string
  description: string
  value: number
  icon: any
  trend?: string
  reach: number
  impressions: number
  engagement: number
  followers_count: number
}

interface Props {
  influencerId: string;
}

export default function InstagramDashboard({ influencerId }: Props) {
  const [media, setMedia] = useState<InstagramMedia[]>([])
  const [insights, setInsights] = useState<InstagramInsights[]>([])
  const [loading, setLoading] = useState(false)

  const loadDashboardData = async () => {
    setLoading(true)
    try {
      // 임시 데이터 사용 - 실제 API 연동 시 교체 필요
      const mediaData: InstagramMedia[] = [];
      const insightsData: InstagramInsights[] = [];
      
      setMedia(mediaData);
      setInsights(insightsData);
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (influencerId) {
      loadDashboardData()
    }
  }, [influencerId])

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
      {loading && (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-gray-600">데이터를 불러오는 중...</span>
        </div>
      )}

      <Tabs defaultValue="media" className="space-y-4">
        <TabsList>
          <TabsTrigger value="media">미디어</TabsTrigger>
          <TabsTrigger value="insights">인사이트</TabsTrigger>
        </TabsList>

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
                    {formatDate(item.timestamp.toString())}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="insights" className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {insights.length > 0 ? insights.map((insight, index) => (
                <Card key={index}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">{insight.title}</CardTitle>
                    <CardDescription className="text-xs">{insight.description}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-blue-600 mb-1">
                      {insight.value || 0}
                    </div>
                    <div className="flex items-center text-xs text-gray-500">
                      <TrendingUp className="w-3 h-3 mr-1" />
                      {insight.trend || '변화 없음'}
                    </div>
                  </CardContent>
                </Card>
              )) : (
                <Card className="col-span-full">
                  <CardContent className="p-6 text-center">
                    <div className="text-gray-500">
                      <TrendingUp className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                      <p className="text-sm">인사이트 데이터가 없거나, 비즈니스 계정이 아닙니다.</p>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
