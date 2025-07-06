import { NextRequest, NextResponse } from 'next/server'

// ComfyUI 생성 진행 상황 확인 API
export async function GET(
  request: NextRequest,
  { params }: { params: { jobId: string } }
) {
  try {
    const jobId = params.jobId
    
    if (!jobId) {
      return NextResponse.json(
        { success: false, error: 'Job ID is required' },
        { status: 400 }
      )
    }

    const comfyUIUrl = process.env.COMFYUI_URL || 'http://localhost:8188'
    
    // ComfyUI 히스토리 확인
    const historyResponse = await fetch(`${comfyUIUrl}/history/${jobId}`)
    
    if (!historyResponse.ok) {
      return NextResponse.json({
        success: true,
        progress: 0,
        status: 'generating',
        message: 'Generation in progress'
      })
    }

    const historyData = await historyResponse.json()
    
    // 작업이 완료되었는지 확인
    if (historyData[jobId]) {
      const job = historyData[jobId]
      
      if (job.status && job.status.completed) {
        // 완료된 경우 생성된 이미지 정보 가져오기
        const outputs = job.outputs
        let imageUrl = null
        let imageName = null
        
        // SaveImage 노드(9번)에서 이미지 정보 찾기
        if (outputs && outputs["9"] && outputs["9"].images && outputs["9"].images.length > 0) {
          const imageInfo = outputs["9"].images[0]
          imageName = imageInfo.filename
          imageUrl = `${comfyUIUrl}/view?filename=${imageName}&type=output`
        }
        
        return NextResponse.json({
          success: true,
          progress: 100,
          status: 'completed',
          image_url: imageUrl,
          image_name: imageName,
          image_id: jobId,
          seed: job.prompt?.seed || Math.floor(Math.random() * 1000000)
        })
      } else if (job.status && job.status.status_str === 'error') {
        return NextResponse.json({
          success: true,
          progress: 0,
          status: 'failed',
          error: 'Generation failed'
        })
      }
    }
    
    // 현재 실행 중인 작업의 진행률 확인
    const queueResponse = await fetch(`${comfyUIUrl}/queue`)
    
    if (queueResponse.ok) {
      const queueData = await queueResponse.json()
      
      // 현재 실행 중인 작업 찾기
      const runningJobs = queueData.queue_running || []
      const pendingJobs = queueData.queue_pending || []
      
      const currentJob = runningJobs.find((job: any) => job[1] === jobId)
      
      if (currentJob) {
        // 실행 중인 작업의 진행률 계산 (대략적)
        return NextResponse.json({
          success: true,
          progress: 50, // 실행 중이면 50%로 표시
          status: 'generating',
          message: 'Generating image...'
        })
      }
      
      const pendingJob = pendingJobs.find((job: any) => job[1] === jobId)
      
      if (pendingJob) {
        // 대기 중인 작업
        return NextResponse.json({
          success: true,
          progress: 10,
          status: 'generating',
          message: 'Waiting in queue...'
        })
      }
    }
    
    // 작업을 찾을 수 없는 경우
    return NextResponse.json({
      success: true,
      progress: 0,
      status: 'generating',
      message: 'Generation starting...'
    })
    
  } catch (error) {
    console.error('Error checking generation progress:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to check generation progress' 
      },
      { status: 500 }
    )
  }
}