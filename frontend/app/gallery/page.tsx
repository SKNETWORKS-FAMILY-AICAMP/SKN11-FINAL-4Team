'use client'

import React, { useState, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Download, Trash2, Search, Filter, ChevronLeft, ChevronRight } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import Image from 'next/image'
import { useToast } from '@/hooks/use-toast'
import { useAuth } from '@/hooks/use-auth'

interface GeneratedImage {
  storage_id: string
  s3_url: string
  group_id: number
  created_at: string
}

interface PaginationInfo {
  page: number
  page_size: number
  total_count: number
  total_pages: number
}

export default function GalleryPage() {
  const { toast } = useToast()
  const { user } = useAuth()
  const [images, setImages] = useState<GeneratedImage[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedTeam, setSelectedTeam] = useState<string>('')
  const [selectedImage, setSelectedImage] = useState<GeneratedImage | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [pagination, setPagination] = useState<PaginationInfo>({
    page: 1,
    page_size: 12,
    total_count: 0,
    total_pages: 0
  })

  // 이미지 목록 가져오기
  const fetchImages = async (page: number = 1) => {
    try {
      setLoading(true)
      const token = localStorage.getItem('access_token')
      if (!token) {
        toast({
          title: "인증 필요",
          description: '로그인이 필요합니다.',
          variant: "destructive",
          duration: 3000,
        })
        return
      }

      // 팀 ID 설정
      const teamId = selectedTeam || (user?.teams?.[0] || '')
      if (!teamId) {
        toast({
          title: "팀 정보 없음",
          description: '소속된 팀이 없습니다.',
          variant: "destructive",
          duration: 3000,
        })
        setLoading(false)
        return
      }

      const params = new URLSearchParams({
        page: page.toString(),
        page_size: '12',
        team_id: teamId.toString()
      })

      const response = await fetch(`/api/v1/gallery/images?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (response.ok) {
        const data = await response.json()
        setImages(data.images || [])
        setPagination(data.pagination || {
          page: 1,
          page_size: 12,
          total_count: 0,
          total_pages: 0
        })
      } else {
        throw new Error('이미지 목록 조회 실패')
      }
    } catch (error) {
      // console.error('Failed to fetch images:', error)
      toast({
        title: "오류 발생",
        description: '이미지 목록을 불러오는데 실패했습니다.',
        variant: "destructive",
        duration: 3000,
      })
    } finally {
      setLoading(false)
    }
  }

  // 페이지 변경
  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= pagination.total_pages) {
      setCurrentPage(newPage)
      fetchImages(newPage)
    }
  }

  // 팀 변경
  const handleTeamChange = (teamId: string) => {
    setSelectedTeam(teamId)
    setCurrentPage(1)
  }

  // 이미지 삭제
  const handleDelete = async (storageId: string) => {
    if (!confirm('이 이미지를 삭제하시겠습니까?')) return

    try {
      const token = localStorage.getItem('access_token')
      if (!token) {
        toast({
          title: "인증 필요",
          description: '로그인이 필요합니다.',
          variant: "destructive",
          duration: 3000,
        })
        return
      }

      const response = await fetch(`/api/v1/gallery/images/${storageId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (response.ok) {
        setImages(prev => prev.filter(img => img.storage_id !== storageId))
        toast({
          title: "삭제 완료",
          description: '이미지가 삭제되었습니다.',
          duration: 3000,
        })
        // 현재 페이지 새로고침
        fetchImages(currentPage)
      } else {
        toast({
          title: "삭제 실패",
          description: '이미지 삭제에 실패했습니다.',
          variant: "destructive",
          duration: 3000,
        })
      }
    } catch (error) {
      // console.error('Failed to delete image:', error)
      toast({
        title: "오류 발생",
        description: '이미지 삭제 중 오류가 발생했습니다.',
        variant: "destructive",
        duration: 3000,
      })
    }
  }

  // 이미지 다운로드
  const handleDownload = async (s3Url: string, storageId: string) => {
    try {
      const response = await fetch(s3Url)
      
      // presigned URL이 만료된 경우 새로 요청
      if (!response.ok && response.status === 403) {
        const newUrl = await fetchNewPresignedUrl(storageId)
        if (newUrl) {
          const newResponse = await fetch(newUrl)
          if (newResponse.ok) {
            const blob = await newResponse.blob()
            downloadBlob(blob, `image-${storageId}.png`)
            return
          }
        }
      } else if (response.ok) {
        const blob = await response.blob()
        downloadBlob(blob, `image-${storageId}.png`)
        return
      }
      
      throw new Error('Download failed')
    } catch (error) {
      // console.error('Failed to download image:', error)
      toast({
        title: "다운로드 실패",
        description: '이미지 다운로드에 실패했습니다.',
        variant: "destructive",
        duration: 3000,
      })
    }
  }

  // Blob을 다운로드하는 헬퍼 함수
  const downloadBlob = (blob: Blob, filename: string) => {
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  }

  // 새로운 presigned URL 가져오기
  const fetchNewPresignedUrl = async (storageId: string): Promise<string | null> => {
    try {
      const token = localStorage.getItem('access_token')
      if (!token) return null

      const response = await fetch(`/api/v1/gallery/images/${storageId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (response.ok) {
        const data = await response.json()
        return data.s3_url
      }
    } catch (error) {
      console.error('Failed to fetch new presigned URL:', error)
    }
    return null
  }

  // 초기 로드 및 팀 변경시 이미지 가져오기
  useEffect(() => {
    if (user && (selectedTeam || user.teams?.length > 0)) {
      fetchImages(1)
    }
  }, [selectedTeam, user])

  // 초기 팀 설정
  useEffect(() => {
    if (user?.teams && user.teams.length > 0 && !selectedTeam) {
      setSelectedTeam(user.teams[0].group_id.toString())
    }
  }, [user])

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-4">이미지 갤러리</h1>
        
        {/* 필터 영역 */}
        <div className="flex gap-4 mb-6">
          {user?.teams && user.teams.length > 1 && (
            <Select value={selectedTeam} onValueChange={handleTeamChange}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="팀 선택" />
              </SelectTrigger>
              <SelectContent>
                {user.teams.map(team => (
                  <SelectItem key={team.group_id} value={team.group_id.toString()}>
                    팀 {team.group_id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          
          <div className="flex items-center text-sm text-gray-600">
            총 {pagination.total_count}개의 이미지
          </div>
        </div>

        {/* 로딩 상태 */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
            <p className="mt-2 text-gray-600">이미지를 불러오는 중...</p>
          </div>
        )}

        {/* 이미지 그리드 */}
        {!loading && images.length === 0 && (
          <div className="text-center py-12 bg-gray-50 rounded-lg">
            <p className="text-gray-500">생성된 이미지가 없습니다.</p>
          </div>
        )}

        {!loading && images.length > 0 && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {images.map((image) => (
                <Card key={image.storage_id} className="overflow-hidden group">
                  <div className="relative aspect-square">
                    <Image
                      src={image.s3_url}
                      alt={`Generated image ${image.storage_id}`}
                      fill
                      className="object-cover cursor-pointer transition-transform group-hover:scale-105"
                      onClick={() => setSelectedImage(image)}
                      onError={async (e) => {
                        const imgElement = e.target as HTMLImageElement
                        const newUrl = await fetchNewPresignedUrl(image.storage_id)
                        if (newUrl) {
                          imgElement.src = newUrl
                          // 이미지 목록에서도 URL 업데이트
                          setImages(prev => prev.map(img => 
                            img.storage_id === image.storage_id 
                              ? { ...img, s3_url: newUrl }
                              : img
                          ))
                        }
                      }}
                    />
                    <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-20 transition-opacity" />
                    <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-2">
                      <Button
                        size="icon"
                        variant="secondary"
                        onClick={() => handleDownload(image.s3_url, image.storage_id)}
                        className="bg-white/90 hover:bg-white"
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="secondary"
                        onClick={() => handleDelete(image.storage_id)}
                        className="bg-white/90 hover:bg-white text-red-600 hover:text-red-700"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  <CardContent className="p-4">
                    <p className="text-xs text-gray-400">
                      {new Date(image.created_at).toLocaleDateString()}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* 페이지네이션 */}
            {pagination.total_pages > 1 && (
              <div className="mt-8 flex justify-center items-center gap-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                  이전
                </Button>
                <span className="text-sm">
                  {currentPage} / {pagination.total_pages} 페이지
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage === pagination.total_pages}
                >
                  다음
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      {/* 이미지 상세 모달 */}
      {selectedImage && (
        <div
          className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedImage(null)}
        >
          <div
            className="relative max-w-4xl max-h-[90vh] bg-white rounded-lg overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="relative">
              <Image
                src={selectedImage.s3_url}
                alt={'Generated image'}
                width={512}
                height={512}
                className="max-h-[70vh] object-contain"
                onError={async (e) => {
                  const imgElement = e.target as HTMLImageElement
                  const newUrl = await fetchNewPresignedUrl(selectedImage.storage_id)
                  if (newUrl) {
                    imgElement.src = newUrl
                    // 선택된 이미지의 URL도 업데이트
                    setSelectedImage(prev => prev ? { ...prev, s3_url: newUrl } : null)
                    // 이미지 목록에서도 URL 업데이트
                    setImages(prev => prev.map(img => 
                      img.storage_id === selectedImage.storage_id 
                        ? { ...img, s3_url: newUrl }
                        : img
                    ))
                  }
                }}
              />
            </div>
            <div className="p-4">
              <h3 className="font-semibold mb-2">이미지 정보</h3>
              <p className="text-sm text-gray-600 mb-1">
                <strong>생성일:</strong> {new Date(selectedImage.created_at).toLocaleString()}
              </p>
              <div className="flex gap-2 mt-4">
                <Button
                  onClick={() => handleDownload(selectedImage.s3_url, selectedImage.storage_id)}
                >
                  <Download className="h-4 w-4 mr-2" />
                  다운로드
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => {
                    handleDelete(selectedImage.storage_id)
                    setSelectedImage(null)
                  }}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  삭제
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}