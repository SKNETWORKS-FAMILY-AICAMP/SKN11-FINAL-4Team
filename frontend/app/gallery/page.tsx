'use client'

import React, { useState, useEffect, useRef } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Download, Trash2, Search, Filter, ChevronLeft, ChevronRight } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import Image from 'next/image'

interface GeneratedImage {
  storage_id?: string
  s3_url?: string
  group_id?: number
  created_at?: string
  updated_at?: string
  team_id?: number
  team_name?: string
  // S3 직접 조회 시 사용되는 필드
  key?: string
  size?: number
  last_modified?: string
  presigned_url?: string
  filename?: string
}

export default function GalleryPage() {
  const [images, setImages] = useState<GeneratedImage[]>([])
  const [filteredImages, setFilteredImages] = useState<GeneratedImage[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedTeam, setSelectedTeam] = useState<string>('all')
  const [teams, setTeams] = useState<{id: number, name: string}[]>([])
  const [selectedImage, setSelectedImage] = useState<GeneratedImage | null>(null)
  const [wsConnected, setWsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const imagesPerPage = 12

  // WebSocket 연결
  const connectWebSocket = () => {
    try {
      const accessToken = localStorage.getItem('access_token')
      if (!accessToken) {
        console.error('No access token found')
        setLoading(false)
        return
      }

      // 이미 연결되어 있으면 재연결하지 않음
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        console.log('WebSocket already connected, skipping reconnection')
        return
      }

      // 기존 연결이 있으면 정리
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }

      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
      const wsProtocol = backendUrl.startsWith('https') ? 'wss:' : 'ws:'
      const wsHost = backendUrl.replace(/^https?:\/\//, '')
      const wsUrl = `${wsProtocol}//${wsHost}/api/v1/image-generation/ws?token=${accessToken}`
      
      console.log('Connecting to WebSocket:', wsUrl)
      const ws = new WebSocket(wsUrl)
      
      ws.onopen = () => {
        console.log('WebSocket connected')
        setWsConnected(true)
        // S3에서 직접 이미지 목록 요청
        ws.send(JSON.stringify({
          type: 'get_s3_images',
          data: {
            folder_path: ''  // 비워두면 모든 팀 폴더 조회
          }
        }))
      }
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('WebSocket message:', data)
          
          if (data.type === 's3_images_list' && data.data.success) {
            // S3 이미지 데이터를 GeneratedImage 형식으로 변환
            const s3Images: GeneratedImage[] = data.data.images.map((img: any) => ({
              key: img.key,
              s3_url: img.presigned_url,
              presigned_url: img.presigned_url,
              filename: img.filename,
              size: img.size,
              last_modified: img.last_modified,
              created_at: img.last_modified,
              team_id: img.team_id,
              team_name: img.team_name,
              storage_id: img.key  // key를 storage_id로 사용
            }))
            
            setImages(s3Images)
            setFilteredImages(s3Images)
            setLoading(false)
            
            // 팀 목록 추출
            const teamMap = new Map<number, string>()
            s3Images.forEach((img: GeneratedImage) => {
              if (img.team_id && img.team_name) {
                teamMap.set(img.team_id, img.team_name)
              }
            })
            
            const uniqueTeams = Array.from(teamMap, ([id, name]) => ({ id, name }))
            setTeams(uniqueTeams)
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        setWsConnected(false)
      }
      
      ws.onclose = () => {
        console.log('WebSocket disconnected')
        setWsConnected(false)
        wsRef.current = null
        
        // 재연결 시도 (연결이 없을 때만)
        setTimeout(() => {
          if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            connectWebSocket()
          }
        }, 3000)
      }
      
      wsRef.current = ws
    } catch (error) {
      console.error('Failed to connect WebSocket:', error)
      setLoading(false)
    }
  }

  useEffect(() => {
    connectWebSocket()
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  // 필터링 효과
  useEffect(() => {
    let filtered = images

    // 팀 필터링
    if (selectedTeam !== 'all') {
      filtered = filtered.filter(img => img.team_id?.toString() === selectedTeam)
    }

    // 검색어 필터링 (created_at 날짜로 검색)
    if (searchTerm) {
      filtered = filtered.filter(img => {
        if (!img.created_at) return false
        const date = new Date(img.created_at)
        return date.toLocaleDateString().includes(searchTerm) ||
               date.toLocaleTimeString().includes(searchTerm)
      })
    }

    setFilteredImages(filtered)
    setCurrentPage(1) // 필터 변경시 첫 페이지로
  }, [searchTerm, selectedTeam, images])

  // 페이지네이션
  const indexOfLastImage = currentPage * imagesPerPage
  const indexOfFirstImage = indexOfLastImage - imagesPerPage
  const currentImages = filteredImages.slice(indexOfFirstImage, indexOfLastImage)
  const totalPages = Math.ceil(filteredImages.length / imagesPerPage)

  const handleDelete = async (storageId: string) => {
    if (!confirm('이 이미지를 삭제하시겠습니까?')) return

    try {
      const token = localStorage.getItem('access_token')
      if (!token) {
        alert('로그인이 필요합니다.')
        return
      }

      const response = await fetch(`/api/image-generation/images/${storageId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })

      if (response.ok) {
        setImages(prev => prev.filter(img => img.storage_id !== storageId))
        alert('이미지가 삭제되었습니다.')
      } else {
        alert('이미지 삭제에 실패했습니다.')
      }
    } catch (error) {
      console.error('Failed to delete image:', error)
      alert('이미지 삭제 중 오류가 발생했습니다.')
    }
  }

  const handleDownload = async (imageUrl: string, filename: string) => {
    try {
      const response = await fetch(imageUrl)
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      // 파일 이름이 있으면 사용하고, 없으면 기본값 사용
      a.download = filename.includes('.') ? filename : `${filename}.png`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('Failed to download image:', error)
      alert('이미지 다운로드에 실패했습니다.')
    }
  }

  const handleImageClick = (image: GeneratedImage) => {
    setSelectedImage(image)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p>이미지를 불러오는 중...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">내 이미지 갤러리</h1>
      
      {/* 필터링 섹션 */}
      <div className="mb-6 flex flex-col md:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
          <Input
            type="text"
            placeholder="날짜로 검색..."
            className="pl-10"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        
        <Select value={selectedTeam} onValueChange={setSelectedTeam}>
          <SelectTrigger className="w-full md:w-[200px]">
            <SelectValue placeholder="팀 선택" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">모든 팀</SelectItem>
            {teams.map(team => (
              <SelectItem key={team.id} value={team.id.toString()}>
                {team.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        
        <div className="text-sm text-gray-500 flex items-center">
          총 {filteredImages.length}개의 이미지
        </div>
      </div>

      {/* 이미지 그리드 */}
      {currentImages.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500">표시할 이미지가 없습니다.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {currentImages.map((image) => (
              <Card key={image.storage_id} className="overflow-hidden hover:shadow-lg transition-shadow">
                <CardContent className="p-0">
                  <div 
                    className="relative aspect-square cursor-pointer"
                    onClick={() => handleImageClick(image)}
                  >
                    <Image
                      src={image.presigned_url || image.s3_url || ''}
                      alt={`Generated image ${image.filename || image.storage_id}`}
                      fill
                      className="object-cover"
                      sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                    />
                  </div>
                  <div className="p-4">
                    <div className="text-xs text-gray-500 mb-2">
                      {new Date(image.created_at || image.last_modified || '').toLocaleString()}
                    </div>
                    {image.filename && (
                      <div className="text-xs text-gray-600 mb-1 truncate">
                        {image.filename}
                      </div>
                    )}
                    {image.team_name && (
                      <div className="text-xs text-blue-600 mb-2">
                        {image.team_name}
                      </div>
                    )}
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleDownload(image.presigned_url || image.s3_url || '', image.filename || image.storage_id || 'image')
                        }}
                      >
                        <Download className="w-4 h-4 mr-1" />
                        다운로드
                      </Button>
                      {/* S3 직접 조회한 이미지는 삭제 버튼 숨김 */}
                      {!image.key && image.storage_id && (
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={(e) => {
                            e.stopPropagation()
                            if (image.storage_id) {
                              handleDelete(image.storage_id)
                            }
                          }}
                        >
                          <Trash2 className="w-4 h-4 mr-1" />
                          삭제
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* 페이지네이션 */}
          {totalPages > 1 && (
            <div className="mt-6 flex justify-center items-center gap-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                disabled={currentPage === 1}
              >
                <ChevronLeft className="w-4 h-4" />
                이전
              </Button>
              
              <span className="text-sm">
                {currentPage} / {totalPages} 페이지
              </span>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                disabled={currentPage === totalPages}
              >
                다음
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          )}
        </>
      )}

      {/* 이미지 상세 모달 */}
      {selectedImage && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedImage(null)}
        >
          <div 
            className="bg-white rounded-lg max-w-4xl max-h-[90vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="relative">
              <Image
                src={selectedImage.presigned_url || selectedImage.s3_url || ''}
                alt={`Generated image ${selectedImage.filename || selectedImage.storage_id}`}
                width={1024}
                height={1024}
                className="w-full h-auto"
              />
              <Button
                className="absolute top-4 right-4"
                variant="secondary"
                size="sm"
                onClick={() => setSelectedImage(null)}
              >
                닫기
              </Button>
            </div>
            <div className="p-4">
              <p className="text-sm text-gray-600">
                생성일: {new Date(selectedImage.created_at || selectedImage.last_modified || '').toLocaleString()}
              </p>
              {selectedImage.team_name && (
                <p className="text-sm text-blue-600">
                  팀: {selectedImage.team_name}
                </p>
              )}
              <div className="mt-4 flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => handleDownload(selectedImage.presigned_url || selectedImage.s3_url || '', selectedImage.filename || selectedImage.storage_id || 'image')}
                >
                  <Download className="w-4 h-4 mr-2" />
                  다운로드
                </Button>
                {/* S3 직접 조회한 이미지는 삭제 버튼 숨김 */}
                {!selectedImage.key && selectedImage.storage_id && (
                  <Button
                    variant="destructive"
                    onClick={() => {
                      if (selectedImage.storage_id) {
                        handleDelete(selectedImage.storage_id)
                      }
                      setSelectedImage(null)
                    }}
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    삭제
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}