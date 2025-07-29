"use client"

import type React from "react"

import { useState, useEffect, useRef } from "react"
import { useRouter } from "next/navigation"
import { Navigation } from "@/components/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ModelService, ToneGenerationRequest, ConversationExample, ModelMBTI } from "@/lib/services/model.service"
import { useAuth } from "@/hooks/use-auth"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Upload, ArrowLeft, Lightbulb, MessageCircle, Trash2 } from "lucide-react"
import Link from "next/link"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { useToast } from "@/hooks/use-toast"

interface FormDataType {
  name: string;
  description: string;
  modelType: string;
  personality: string;
  tone: string;
  customTones: string[];
  mbti: string;
  gender: string;
  age: string;
  imageMethod: string;
  selectedPresetId: string;
  huggingFaceToken: string;
  systemPrompt: string;
}

export default function CreateModelPage() {
  const { toast } = useToast()
  const fetchedRef = useRef(false)
  const [formData, setFormData] = useState<FormDataType>({
    name: "",
    description: "",
    modelType: "", // "character" 또는 "human" 또는 "object"
    personality: "",
    tone: "",
    customTones: [],
    mbti: "",
    gender: "",
    age: "",
    imageMethod: "upload", // 항상 upload로 고정
    selectedPresetId: "manual", // 기본값을 "manual"로 설정하여 직접 입력 모드 시작
    huggingFaceToken: "",
    systemPrompt: "", // systemPrompt 필드 추가
  })
  const [files, setFiles] = useState({
    imageSamples: null as File[] | null,
  })
  const [imagePreviewUrls, setImagePreviewUrls] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [toneTab, setToneTab] = useState("recommend")
  const [stylePresets, setStylePresets] = useState<any[]>([])
  const [loadingPresets, setLoadingPresets] = useState(false)
  const router = useRouter()
  const { user } = useAuth()
  const [showToneExamples, setShowToneExamples] = useState(false)
  const [customToneInput, setCustomToneInput] = useState("")
  const [generatingTones, setGeneratingTones] = useState(false)
  const [generatedTones, setGeneratedTones] = useState<ConversationExample[]>([])
  const [huggingFaceTokens, setHuggingFaceTokens] = useState<any[]>([])
  const [loadingTokens, setLoadingTokens] = useState(false)
  const [mbtiList, setMbtiList] = useState<ModelMBTI[]>([])
  const [loadingMbti, setLoadingMbti] = useState(false)
  const [toneType, setToneType] = useState<"tone" | "dialogue">("tone") // 말투 타입 추가

  useEffect(() => {
    // 중복 API 호출 방지
    if (fetchedRef.current) return;
    fetchedRef.current = true;

    // 실제 API에서 프리셋 데이터 가져오기
    const fetchStylePresets = async () => {
      setLoadingPresets(true);

      try {
        const presets = await ModelService.getStylePresets();
        setStylePresets(presets);
      } catch (error) {
        // 프리셋 데이터 로드 실패 처리
        console.error('프리셋 데이터 로드 실패:', error);
        toast({
          title: "프리셋 로드 실패",
          description: "스타일 프리셋을 불러오는 데 실패했습니다.",
          variant: "destructive",
          duration: 3000,
        });
      } finally {
        setLoadingPresets(false);
      }
    };

    // 허깅페이스 토큰 데이터 가져오기
    const fetchHuggingFaceTokens = async () => {
      if (!user || !user.teams || user.teams.length === 0) {
        return;
      }

      setLoadingTokens(true);

      try {
        const tokens = await ModelService.getHuggingFaceTokens(user.teams[0].group_id);
        setHuggingFaceTokens(tokens);
        
        // 토큰이 있고 기본값이 설정되지 않은 경우 첫 번째 토큰을 기본값으로 설정
        if (tokens.length > 0 && !formData.huggingFaceToken) {
          setFormData(prev => ({ ...prev, huggingFaceToken: tokens[0].hf_manage_id }));
        }
      } catch (error) {
        // 허깅페이스 토큰 데이터 로드 실패 처리
      } finally {
        setLoadingTokens(false);
      }
    };

    // MBTI 목록 가져오기
    const fetchMbtiList = async () => {
      setLoadingMbti(true);
      try {
        const mbtiData = await ModelService.getMBTIList();
        setMbtiList(mbtiData);
      } catch (error) {
        // MBTI 데이터 로드 실패 처리
      } finally {
        setLoadingMbti(false);
      }
    };

    fetchStylePresets();
    fetchHuggingFaceTokens();
    fetchMbtiList();
  }, [user]) // user가 변경될 때마다 토큰 다시 가져오기

  // 성격(personality)이 바뀌면 추천 말투 숨김
  useEffect(() => {
    setShowToneExamples(false);
  }, [formData.personality]);
  
  // 탭 변경 시 tone type 설정
  useEffect(() => {
    if (toneTab === "custom") {
      setToneType("dialogue");
    } else {
      setToneType("tone");
    }
  }, [toneTab]);

  // customTone이 있으면 customTones로 마이그레이션
  useEffect(() => {
    if (formData.tone && !formData.customTones.length) {
      setFormData((prev) => ({ ...prev, customTones: [prev.tone] }));
    }
  }, [formData.tone]);

  const handleInputChange = (field: string, value: string | string[]) => {
    setFormData((prev) => {
      // imageMethod 변경 관련 로직 제거 (항상 upload로 고정)
      
      // 일반적인 필드 변경
      return {
        ...prev,
        [field]: value,
      }
    })
  }

  const handleFileUpload = async (type: keyof typeof files, uploadedFiles: FileList | null) => {
    if (uploadedFiles) {
      const fileArray = Array.from(uploadedFiles)
      setFiles((prev) => ({ ...prev, [type]: fileArray }))
      
      // 이미지 미리보기 URL 생성
      if (type === 'imageSamples') {
        const urls = fileArray.map(file => URL.createObjectURL(file))
        setImagePreviewUrls(urls)
        // 이미지 파일들을 상태에 저장 (인플루언서 생성 시 함께 업로드)
        // console.log('이미지 파일 선택됨:', fileArray.length, '개');
      }
    }
  }

  // 프리셋 선택 핸들러
  const handlePresetSelect = async (presetId: string) => {
    if (presetId === "manual") {
      setToneTab("recommend"); // 직접 입력 시 추천 말투 탭으로
      setFormData(prev => ({
        ...prev,
        selectedPresetId: "manual",
        // 직접 입력 모드로 전환 시 관련 필드 초기화 (선택 사항)
        modelType: "",
        personality: "",
        tone: "",
        customTones: [],
        mbti: "",
        gender: "",
        age: "",
        hairStyle: "",
        mood: "",
        systemPrompt: "",
        description: "",
      }));
      setGeneratedTones([]); // 직접 입력 시 생성된 말투 초기화
      setShowToneExamples(false); // 직접 입력 시 추천 말투 숨김
      return;
    }

    setLoadingPresets(true);
    try {
      const preset = await ModelService.getStylePresetById(presetId);
      if (preset) {
        setToneTab("custom"); // 프리셋 선택 시 직접 입력 탭으로 (프리셋 말투 확인용)
        setFormData(prev => ({
          ...prev,
          selectedPresetId: presetId,
          name: preset.style_preset_name || "",
          description: preset.influencer_description || "",
          modelType: preset.influencer_type === 1 ? "character" : preset.influencer_type === 2 ? "human" : "objects",
          personality: preset.influencer_personality || "",
          tone: preset.influencer_speech || "",
          customTones: [preset.influencer_speech || ""],
          mbti: preset.mbti_id ? String(preset.mbti_id) : "none",
          gender: String(preset.influencer_gender),
          age: preset.influencer_age_group ? String(preset.influencer_age_group * 10) : "",
          imageMethod: "upload", // 항상 upload로 고정
          systemPrompt: preset.system_prompt || "",
        }));
        setGeneratedTones([{
          title: preset.style_preset_name,
          example: "프리셋에 정의된 말투입니다.",
          tone: preset.influencer_speech,
          hashtags: "",
          system_prompt: preset.system_prompt || ""
        }]);
        setShowToneExamples(true);
      }
    } catch (e) {
      toast({
        title: "오류 발생",
        description: "프리셋 정보를 불러오지 못했습니다.",
        variant: "destructive",
        duration: 3000,
      });
    } finally {
      setLoadingPresets(false);
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // 프리셋 모드 검증
    if (formData.selectedPresetId && formData.selectedPresetId !== "manual") {
      if (!formData.selectedPresetId) {
        toast({
          title: "선택 필요",
          description: "프리셋을 선택해주세요.",
          variant: "destructive",
          duration: 3000,
        })
        return
      }
    } else {
      // 직접 입력 모드 검증
      if (!formData.modelType && !formData.imageMethod) {
        toast({
          title: "선택 필요",
          description: "모델 유형을 선택해주세요.",
          variant: "destructive",
          duration: 3000,
        });
        return;
      }
      if (!formData.personality.trim()) {
        toast({
          title: "입력 필요",
          description: "성격을 입력해주세요.",
          variant: "destructive",
          duration: 3000,
        });
        return;
      }
      // 말투 검증: 추천 말투 탭에서는 tone 확인, 대사 입력 탭에서는 7개 이상 확인
      if (toneTab === "recommend" && !formData.tone.trim()) {
        toast({
          title: "선택 필요",
          description: "추천 말투를 선택해주세요.",
          variant: "destructive",
          duration: 3000,
        });
        return;
      }
      
      if (toneTab === "custom" && formData.customTones.length < 7) {
        toast({
          title: "대사 부족",
          description: `최소 7개의 대사를 입력해주세요. (현재 ${formData.customTones.length}개)`,
          variant: "destructive",
          duration: 3000,
        });
        return;
      }

      // 이미지 검증 (업로드만 허용)
      const hasImageUpload = files.imageSamples && files.imageSamples.length > 0;

      if (!hasImageUpload) {
        toast({
          title: "입력 필요",
          description: "이미지를 업로드해주세요.",
          variant: "destructive",
          duration: 3000,
        });
        return;
      }
    }

    setIsLoading(true)

    try {
      // 사용자 인증 확인
      if (!user || !user.teams || user.teams.length === 0) {
        toast({
          title: "권한 없음",
          description: "팀에 소속되어야 인플루언서를 생성할 수 있습니다.",
          variant: "destructive",
          duration: 3000,
        })
        setIsLoading(false)
        return
      }

      // 백엔드 API 호출 데이터 준비
      const createInfluencerData: any = {
        user_id: user.user_id,
        group_id: user.teams[0].group_id, // 첫 번째 팀의 group_id 사용
        influencer_name: formData.name,
        influencer_description: formData.description,
        image_url: undefined,
        influencer_data_url: undefined,
        learning_status: 0, // 초기 상태
        influencer_model_repo: "",
        chatbot_option: false,
        hf_manage_id: formData.huggingFaceToken !== "none" ? formData.huggingFaceToken : undefined, // 허깅페이스 토큰 ID 추가
      }

      // 프리셋 선택 여부에 따른 데이터 추가
      if (formData.selectedPresetId !== "manual") {
        // 프리셋 선택 모드: style_preset_id와 프리셋 데이터 사용
        const selectedPreset = stylePresets.find(p => p.style_preset_id === formData.selectedPresetId);
        if (selectedPreset) {
          createInfluencerData.style_preset_id = formData.selectedPresetId;
          createInfluencerData.personality = selectedPreset.influencer_personality;
          createInfluencerData.tone = selectedPreset.influencer_speech;
          createInfluencerData.system_prompt = formData.systemPrompt || selectedPreset.system_prompt; // 프리셋의 시스템 프롬프트 추가
          createInfluencerData.model_type = selectedPreset.influencer_type === 1 ? "character" : selectedPreset.influencer_type === 2 ? "human" : "objects";
          createInfluencerData.mbti = selectedPreset.mbti_name;
          createInfluencerData.mbti_id = selectedPreset.mbti_id;
          createInfluencerData.gender = selectedPreset.influencer_gender === 0 ? "male" : selectedPreset.influencer_gender === 1 ? "female" : "other";
          createInfluencerData.age = selectedPreset.influencer_age_group ? String(selectedPreset.influencer_age_group * 10) : undefined;
          createInfluencerData.hair_style = selectedPreset.influencer_hairstyle;
          createInfluencerData.mood = selectedPreset.influencer_style;
        }
      } else {
        // 직접 입력 모드: style_preset_id는 undefined로 보내고, 사용자가 입력한 데이터 사용
        createInfluencerData.style_preset_id = undefined; // 백엔드에서 자동 생성 로직을 타도록 undefined로 보냄
        createInfluencerData.personality = formData.personality;
        
        // 탭에 따라 데이터 전송 방식 변경
        if (toneTab === "custom" && formData.customTones.length >= 7) {
          // 대사 입력 탭: tone_data로 전송
          createInfluencerData.tone_type = "dialogue";
          createInfluencerData.tone_data = formData.customTones.join("\n");
          createInfluencerData.tone = ""; // tone은 빈 값으로
        } else {
          // 추천 말투 탭: 기존 방식대로 tone 필드 사용
          createInfluencerData.tone = formData.tone || "";
        }
        
        createInfluencerData.system_prompt = formData.systemPrompt; // Use the stored systemPrompt
        createInfluencerData.model_type = formData.modelType;
        // mbti_id를 MBTI 타입 문자열로 변환
        if (formData.mbti !== "none" && formData.mbti) {
          const selectedMbti = mbtiList.find(m => String(m.mbti_id) === formData.mbti);
          createInfluencerData.mbti = selectedMbti?.mbti_name;
          createInfluencerData.mbti_id = parseInt(formData.mbti);
        }
        createInfluencerData.gender = formData.gender !== "none" ? (formData.gender === "0" ? "male" : formData.gender === "1" ? "female" : formData.gender === "2" ? "other" : formData.gender) : undefined;
        createInfluencerData.age = formData.age;

        // 이미지 생성 관련 코드 제거
      }

      // 이미지가 있는 경우 FormData로 전송
      if (files.imageSamples && files.imageSamples.length > 0) {
        const formData = new FormData();
        
        // 인플루언서 데이터를 JSON 문자열로 변환하여 추가
        formData.append('influencer_data', JSON.stringify(createInfluencerData));
        
        // 첫 번째 이미지 파일 추가
        formData.append('image', files.imageSamples[0]);
        
        // ModelService의 createInfluencerWithImage 메서드 사용
        await ModelService.createInfluencerWithImage(formData);
      } else {
        // 이미지가 없는 경우 기존 방식으로 전송
        await ModelService.createInfluencer(createInfluencerData);
      }

      // 성공 알림 표시
      let successMessage = `🎉 AI 인플루언서 "${formData.name}"가 생성되었습니다!\n\n`

      if (formData.selectedPresetId !== "manual") {
        const selectedPreset = stylePresets.find(p => p.style_preset_id === formData.selectedPresetId)
        successMessage += `• 프리셋 기반으로 생성: ${selectedPreset?.style_preset_name}\n`
        successMessage += `• 성격: ${selectedPreset?.influencer_personality}\n`
        successMessage += `• 말투: ${selectedPreset?.influencer_speech}\n`
      } else {
        successMessage += `• 직접 입력으로 생성\n`
        successMessage += `• 성격: ${formData.personality}\n`
        successMessage += `• 말투: ${formData.tone || formData.customTones[0] || "사용자 정의"}\n`
        successMessage += `• 모델 유형: ${formData.modelType === "character" ? "캐릭터형" : formData.modelType === "human" ? "사람형" : "사물형"}\n`

        successMessage += `• 이미지: 파일 업로드\n`
      }

      successMessage += `\n인플루언서 생성 완료 시 이메일과 웹 알림을 받으실 수 있습니다.`

      toast({
        title: "생성 성공",
        description: successMessage,
        duration: 3000,
      })

      setIsLoading(false)
      router.push("/dashboard")

    } catch (error) {
      // console.error('인플루언서 생성 실패:', error)
      setIsLoading(false)

      // 에러 알림 표시
      toast({
        title: "생성 실패",
        description: `오류: ${error instanceof Error ? error.message : '알 수 없는 오류'}. 다시 시도해주세요.`,
        variant: "destructive",
        duration: 3000,
      })
    }
  }

  // API를 통한 말투 생성
  const generateConversationExamples = async (personality: string, isRegeneration: boolean = false) => {
    if (!personality.trim()) {
      toast({
        title: "입력 필요",
        description: '성격을 먼저 입력해주세요.',
        variant: "destructive",
        duration: 3000,
      })
      return
    }
    if (!user || !user.user_id) {
      toast({
        title: "인증 필요",
        description: '사용자 정보가 없어 말투를 생성할 수 없습니다. 로그인 후 다시 시도해주세요.',
        variant: "destructive",
        duration: 3000,
      });
      return;
    }
    if (!user.teams || user.teams.length === 0) {
      toast({
        title: "팀 정보 필요",
        description: '팀 정보가 없어 말투를 생성할 수 없습니다. 팀에 소속된 후 다시 시도해주세요.',
        variant: "destructive",
        duration: 3000,
      });
      return;
    }

    setGeneratingTones(true)

    try {
      const request: ToneGenerationRequest = {
        personality: personality,
        name: formData.name || undefined,
        description: formData.description || undefined,
        mbti: formData.mbti !== "none" ? mbtiList.find(m => String(m.mbti_id) === formData.mbti)?.mbti_name : undefined,
        gender: formData.gender !== "none" ? (formData.gender === "0" ? "male" : formData.gender === "1" ? "female" : formData.gender === "2" ? "other" : formData.gender) : undefined,
        age: formData.age || undefined
      }

      const response = isRegeneration
        ? await ModelService.regenerateTones(request)
        : await ModelService.generateTones(request)

      setGeneratedTones(response.conversation_examples)
      setShowToneExamples(true)

    } catch (error) {
      // console.error('말투 생성 실패:', error)
      toast({
        title: "생성 실패",
        description: '말투 생성에 실패했습니다. 다시 시도해주세요.',
        variant: "destructive",
        duration: 3000,
      })
    } finally {
      setGeneratingTones(false)
    }
  }

  // 기존 로직 (하드코딩된 예시)
  const generateStaticConversationExamples = (personality: string) => {
    if (!(personality || '').trim()) return []
    const personalityLower = (personality || '').toLowerCase()

    // 성격 키워드에 따른 대화 예시
    const conversationMap: Record<string, Array<{ title: string, example: string, tone: string, hashtags?: string, system_prompt?: string }>> = {
      친근: [
        {
          title: "친근하고 다정한",
          example: "안녕하세요! 오늘도 좋은 하루 보내고 계시나요? 😊\n\n저는 오늘 정말 특별한 것을 발견했는데, 여러분과 함께 나누고 싶어서 급하게 글을 써봤어요!",
          tone: "친근하고 다정한",
          hashtags: "#친근 #다정 #일상",
          system_prompt: "당신은 친근하고 다정한 말투를 사용하는 AI 인플루언서입니다."
        },
        {
          title: "편안하고 따뜻한",
          example: "여러분 안녕하세요~ 💕\n\n오늘은 정말 좋은 날씨네요! 이런 날에는 가벼운 산책이나 카페에서 여유롭게 시간을 보내는 것도 좋을 것 같아요.",
          tone: "편안하고 따뜻한",
          hashtags: "#편안 #따뜻 #여유",
          system_prompt: "당신은 편안하고 따뜻한 말투를 사용하는 AI 인플루언서입니다."
        },
        {
          title: "가까운 친구 같은",
          example: "야! 오늘 진짜 대박인 일이 있었어! 🤩\n\n너희들도 꼭 알아야 할 것 같아서 바로 공유하는 거야. 정말 신기했어!",
          tone: "가까운 친구 같은",
          hashtags: "#친구 #대박 #공유",
          system_prompt: "당신은 가까운 친구처럼 편안하게 대화하는 AI 인플루언서입니다."
        }
      ],
      전문: [
        {
          title: "정중하고 전문적인",
          example: "안녕하세요, 여러분.\n\n오늘은 [주제]에 대해 자세히 알아보겠습니다. 전문적인 관점에서 분석한 내용을 공유드리겠습니다.",
          tone: "정중하고 전문적인",
          hashtags: "#전문 #정중 #분석",
          system_prompt: "당신은 정중하고 전문적인 말투를 사용하는 AI 인플루언서입니다."
        },
        {
          title: "신뢰할 수 있는",
          example: "안녕하세요.\n\n검증된 정보를 바탕으로 [주제]에 대한 정확한 분석 결과를 말씀드리겠습니다.",
          tone: "신뢰할 수 있는",
          hashtags: "#신뢰 #정확 #정보",
          system_prompt: "당신은 신뢰할 수 있는 말투를 사용하는 AI 인플루언서입니다."
        },
        {
          title: "지식이 풍부한",
          example: "안녕하세요.\n\n[주제]에 대한 심도 있는 연구 결과를 바탕으로 여러분께 유용한 정보를 제공하겠습니다.",
          tone: "지식이 풍부한",
          hashtags: "#지식 #연구 #유용",
          system_prompt: "당신은 지식이 풍부한 말투를 사용하는 AI 인플루언서입니다."
        }
      ],
      활발: [
        {
          title: "에너지 넘치는",
          example: "안녕하세요 여러분! 🔥\n\n오늘은 정말 대박인 소식을 들고 왔어요! 너무 신나서 바로 공유하고 싶었어요!",
          tone: "에너지 넘치는",
          hashtags: "#에너지 #활발 #신남",
          system_prompt: "당신은 에너지 넘치는 말투를 사용하는 AI 인플루언서입니다."
        },
        {
          title: "밝고 긍정적인",
          example: "안녕하세요! ✨\n\n오늘도 정말 좋은 하루네요! 여러분과 함께 이런 좋은 정보를 나눌 수 있어서 정말 행복해요!",
          tone: "밝고 긍정적인",
          hashtags: "#밝음 #긍정 #행복",
          system_prompt: "당신은 밝고 긍정적인 말투를 사용하는 AI 인플루언서입니다."
        },
        {
          title: "열정적이고 활기찬",
          example: "여러분 안녕하세요! 🎉\n\n오늘은 정말 특별한 순간을 여러분과 함께 나누고 싶어요! 너무 흥미진진해요!",
          tone: "열정적이고 활기찬",
          hashtags: "#열정 #활기 #흥미",
          system_prompt: "당신은 열정적이고 활기찬 말투를 사용하는 AI 인플루언서입니다."
        }
      ],
      차분: [
        {
          title: "차분하고 안정적인",
          example: "안녕하세요.\n\n오늘은 [주제]에 대해 차분히 생각해보는 시간을 가져보겠습니다.",
          tone: "차분하고 안정적인",
          hashtags: "#차분 #안정 #생각",
          system_prompt: "당신은 차분하고 안정적인 말투를 사용하는 AI 인플루언서입니다."
        },
        {
          title: "신중하고 사려깊은",
          example: "안녕하세요.\n\n[주제]에 대해 깊이 있게 고민해보았습니다. 여러분과 함께 생각을 나누고 싶어요.",
          tone: "신중하고 사려깊은",
          hashtags: "#신중 #사려 #고민",
          system_prompt: "당신은 신중하고 사려깊은 말투를 사용하는 AI 인플루언서입니다."
        },
        {
          title: "평온하고 여유로운",
          example: "안녕하세요.\n\n오늘은 여유롭게 [주제]에 대해 이야기해보는 시간을 가져보겠습니다.",
          tone: "평온하고 여유로운",
          hashtags: "#평온 #여유 #대화",
          system_prompt: "당신은 평온하고 여유로운 말투를 사용하는 AI 인플루언서입니다."
        }
      ],
      유머: [
        {
          title: "재치있고 유머러스한",
          example: "안녕하세요 여러분! 😄\n\n오늘은 정말 재미있는 일이 있었는데, 여러분도 웃으실 것 같아서 공유해요!",
          tone: "재치있고 유머러스한",
          hashtags: "#재치 #유머 #재미",
          system_prompt: "당신은 재치있고 유머러스한 말투를 사용하는 AI 인플루언서입니다."
        },
        {
          title: "웃음을 주는",
          example: "여러분 안녕하세요! 😂\n\n오늘은 정말 웃음이 나오는 상황을 겪었어요. 여러분도 함께 웃어주세요!",
          tone: "웃음을 주는",
          hashtags: "#웃음 #재미 #상황",
          system_prompt: "당신은 웃음을 주는 말투를 사용하는 AI 인플루언서입니다."
        },
        {
          title: "밝고 재미있는",
          example: "안녕하세요! 🎭\n\n오늘은 정말 재미있는 이야기를 들고 왔어요! 여러분도 즐거워하실 것 같아요!",
          tone: "밝고 재미있는",
          hashtags: "#밝음 #재미 #이야기",
          system_prompt: "당신은 밝고 재미있는 말투를 사용하는 AI 인플루언서입니다."
        }
      ]
    }

    // 성격에서 키워드 찾기
    const matchedConversations: Array<{ title: string, example: string, tone: string, hashtags?: string, system_prompt?: string }> = []
    Object.keys(conversationMap).forEach((key) => {
      if (personalityLower.includes(key)) {
        matchedConversations.push(...conversationMap[key])
      }
    })

    // 매칭되는 것이 없으면 기본 예시 제공
    if (matchedConversations.length === 0) {
      return [
        {
          title: "친근하고 다정한",
          example: "안녕하세요! 오늘도 좋은 하루 보내고 계시나요? 😊\n\n저는 오늘 정말 특별한 것을 발견했는데, 여러분과 함께 나누고 싶어서 급하게 글을 써봤어요!",
          tone: "친근하고 다정한",
          hashtags: "#친근 #다정 #일상",
          system_prompt: "당신은 친근하고 다정한 말투를 사용하는 AI 인플루언서입니다."
        },
        {
          title: "정중하고 전문적인",
          example: "안녕하세요, 여러분.\n\n오늘은 [주제]에 대해 자세히 알아보겠습니다. 전문적인 관점에서 분석한 내용을 공유드리겠습니다.",
          tone: "정중하고 전문적인",
          hashtags: "#전문 #정중 #분석",
          system_prompt: "당신은 정중하고 전문적인 말투를 사용하는 AI 인플루언서입니다."
        },
        {
          title: "밝고 긍정적인",
          example: "안녕하세요! ✨\n\n오늘도 정말 좋은 하루네요! 여러분과 함께 이런 좋은 정보를 나눌 수 있어서 정말 행복해요!",
          tone: "밝고 긍정적인",
          hashtags: "#밝음 #긍정 #행복",
          system_prompt: "당신은 밝고 긍정적인 말투를 사용하는 AI 인플루언서입니다."
        }
      ]
    }

    // 중복 제거하고 최대 3개까지
    const uniqueConversations = matchedConversations.filter((item, index, self) =>
      index === self.findIndex(t => t.title === item.title)
    )
    return uniqueConversations.slice(0, 3)
  }

  const conversationExamples = generatedTones.length > 0 ? generatedTones : generateStaticConversationExamples(formData.personality)

  // 프리셋 기반 동적 옵션 추출은 현재 사용되지 않음 (주석 처리)
  // const uniqueModelTypes = Array.from(new Set(stylePresets.map(p => p.influencer_type))).filter(Boolean);
  // const uniqueModelTypeOptions = uniqueModelTypes.map(type => ({
  //   value: String(type),
  //   label: type === 1 ? "캐릭터" : type === 2 ? "사람" : type === 3 ? "사물" : `기타(${type})`
  // }));
  // const uniqueGenders = Array.from(new Set(stylePresets.map(p => p.influencer_gender))).filter(Boolean);
  // const uniqueGenderOptions = uniqueGenders.map(gender => ({
  //   value: String(gender),
  //   label: gender === 0 ? "남성" : gender === 1 ? "여성" : gender === 2 ? "기타" : `기타(${gender})`
  // }));
  // const uniqueAges = Array.from(new Set(stylePresets.map(p => p.influencer_age_group))).filter(Boolean);
  // const uniqueAgeOptions = uniqueAges.map(age => ({
  //   value: String(age),
  //   label: age === 1 ? "10대" : age === 2 ? "20대" : age === 3 ? "30대" : age === 4 ? "40대" : age === 5 ? "50대 이상" : `기타(${age})`
  // }));
  // const uniquePersonalities = Array.from(new Set(stylePresets.map(p => p.influencer_personality).filter(Boolean)));
  // const uniqueTones = Array.from(new Set(stylePresets.map(p => p.influencer_speech).filter(Boolean)));

  // 말투 추가 함수
  const handleAddCustomTone = () => {
    const value = customToneInput.trim();
    if (!value) return;
    setFormData((prev) => ({
      ...prev,
      customTones: [...(prev.customTones || []), value],
    }));
    setCustomToneInput("");
  };

  // 말투 삭제 함수
  const handleRemoveCustomTone = (idx: number) => {
    setFormData((prev) => ({
      ...prev,
      customTones: prev.customTones.filter((_, i) => i !== idx),
    }));
  };

  // 이미지 미리보기 URL 정리
  useEffect(() => {
    return () => {
      imagePreviewUrls.forEach(url => URL.revokeObjectURL(url))
    }
  }, [imagePreviewUrls])

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <Link href="/dashboard" className="inline-flex items-center text-blue-600 hover:text-blue-800 mb-4">
            <ArrowLeft className="h-4 w-4 mr-2" />
            대시보드로 돌아가기
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">새 AI 인플루언서 생성</h1>
          <p className="text-gray-600 mt-2">AI 인플루언서의 특성과 학습 데이터를 설정하세요</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-8">
          {/* 프리셋 선택 및 상세 정보 카드 */}
          <Card>
            <CardHeader>
              <CardTitle>기본 정보</CardTitle>
              <CardDescription>AI 인플루언서의 이름, 설명 등 정보를 입력하세요</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* 이름/설명 입력 */}
              <div>
                <Label htmlFor="name">AI 인플루언서 이름*</Label>
                <Input
                  id="name"
                  placeholder="예: 패션 인플루언서 AI"
                  value={formData.name}
                  onChange={(e) => handleInputChange("name", e.target.value)}
                  required
                />
              </div>
              <div>
                <Label htmlFor="description">설명*</Label>
                <Textarea
                  id="description"
                  placeholder="AI 인플루언서에 대한 상세한 설명을 입력하세요"
                  value={formData.description}
                  onChange={(e) => handleInputChange("description", e.target.value)}
                  rows={3}
                  required
                />
              </div>
              {/* 프리셋 불러오기 Select (설명 아래로 이동) */}
              <div>
                <Label>프리셋 불러오기</Label>
                <Select
                  value={formData.selectedPresetId || "manual"}
                  onValueChange={presetId => handlePresetSelect(presetId)}
                  disabled={loadingPresets}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={
                      loadingPresets
                        ? "프리셋 로딩 중..."
                        : "프리셋을 선택하면 아래 입력란이 자동으로 채워집니다"
                    } />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="manual">직접 입력</SelectItem>
                    {stylePresets.map(preset => (
                      <SelectItem key={preset.style_preset_id} value={preset.style_preset_id}>
                        {preset.style_preset_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {loadingPresets && (
                  <p className="text-xs text-gray-500 mt-1">프리셋 데이터를 불러오는 중...</p>
                )}
              </div>
              {/* 아래 입력란은 항상 노출, 프리셋 선택 시 값만 자동 채움 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label htmlFor="mbti">MBTI (선택사항)</Label>
                  <Select value={formData.mbti} onValueChange={(value) => handleInputChange("mbti", value)}>
                    <SelectTrigger>
                      <SelectValue placeholder={loadingMbti ? "MBTI 로딩 중..." : "MBTI 선택 (선택사항)"} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">선택 안함</SelectItem>
                      {mbtiList.map((mbti) => (
                        <SelectItem key={mbti.mbti_id} value={String(mbti.mbti_id)}>
                          {mbti.mbti_name} - {mbti.mbti_traits}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {loadingMbti && (
                    <p className="text-xs text-gray-500 mt-1">MBTI 목록을 불러오는 중...</p>
                  )}
                </div>
                <div>
                  <Label htmlFor="gender">성별*</Label>
                  <Select value={formData.gender} onValueChange={(value) => handleInputChange("gender", value)}>
                    <SelectTrigger>
                      <SelectValue placeholder="성별을 선택하세요" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="0">남성</SelectItem>
                      <SelectItem value="1">여성</SelectItem>
                      <SelectItem value="2">기타</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="age">나이 (선택사항, 20살 이상)</Label>
                  <Input
                    id="age"
                    type="number"
                    placeholder="나이 입력 (20살 이상)"
                    value={formData.age}
                    onChange={(e) => handleInputChange("age", e.target.value)}
                    min="20"
                  />
                </div>
              </div>
              {/* 허깅페이스 토큰 선택 */}
              <div>
                <Label htmlFor="huggingFaceToken">허깅페이스 토큰 선택*</Label>
                <Select value={formData.huggingFaceToken} onValueChange={(value) => handleInputChange("huggingFaceToken", value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="허깅페이스 토큰을 선택하세요" />
                  </SelectTrigger>
                  <SelectContent>
                    {huggingFaceTokens.map(token => (
                      <SelectItem key={token.hf_manage_id} value={token.hf_manage_id}>
                        {token.hf_token_nickname}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {loadingTokens && (
                  <p className="text-xs text-gray-500 mt-1">토큰 목록을 불러오는 중...</p>
                )}
                {!loadingTokens && huggingFaceTokens.length === 0 && (
                  <p className="text-xs text-gray-500 mt-1">사용 가능한 허깅페이스 토큰이 없습니다.</p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* 성격 및 말투 설정 - 직접 입력 모드일 때만 표시 */}
          <Card>
            <CardHeader>
              <CardTitle>성격 및 말투</CardTitle>
              <CardDescription>AI 인플루언서의 성격과 커뮤니케이션 스타일을 정의하세요</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <Label htmlFor="personality">성격*</Label>
                <Input
                  id="personality"
                  placeholder="예: 친근하고 트렌디한, 전문적이고 신뢰할 수 있는, 활발하고 에너지 넘치는"
                  value={formData.personality}
                  onChange={(e) => handleInputChange("personality", e.target.value)}
                  required
                />
                <p className="text-xs text-gray-500 mt-1">💡 성격을 입력하면 아래 대화 예시가 자동으로 생성됩니다</p>
              </div>

              <div>
                <Label className="text-base font-medium">말투 선택*</Label>
                <p className="text-sm text-gray-600 mb-4">성격에 맞는 말투를 선택하거나 직접 입력하세요</p>
                <Tabs value={toneTab} onValueChange={setToneTab} className="w-full mb-4">
                  <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="recommend">추천 말투 선택</TabsTrigger>
                    <TabsTrigger value="custom">캐릭터 대사 입력 (7개 이상)</TabsTrigger>
                  </TabsList>
                  <TabsContent value="recommend">
                    <div className="flex gap-2 mb-4">
                      <Button
                        onClick={() => generateConversationExamples(formData.personality, false)}
                        disabled={!formData.personality.trim() || generatingTones}
                        type="button"
                      >
                        {generatingTones ? '생성 중...' : '말투 생성'}
                      </Button>

                      {showToneExamples && (
                        <Button
                          variant="outline"
                          onClick={() => generateConversationExamples(formData.personality, true)}
                          disabled={!formData.personality.trim() || generatingTones}
                          type="button"
                        >
                          {generatingTones ? '재생성 중...' : '말투 재생성'}
                        </Button>
                      )}
                    </div>
                    {showToneExamples && conversationExamples.length > 0 ? (
                      <div className="space-y-4 mb-4">
                        <div className="flex items-center space-x-2 text-sm text-blue-600">
                          <Lightbulb className="h-4 w-4" />
                          <span>성격 기반 추천 말투</span>
                        </div>
                        <div className="grid grid-cols-1 gap-4">
                          {conversationExamples.map((example, index) => (
                            <Card
                              key={index}
                              className={`cursor-pointer transition-all hover:shadow-md ${formData.tone === example.tone ? 'ring-2 ring-blue-500 bg-blue-50' : ''}`}
                              onClick={() => {
                                handleInputChange("tone", example.tone)
                                handleInputChange("customTones", [] as string[])
                                handleInputChange("systemPrompt", example.system_prompt || "")
                              }}
                            >
                              <CardHeader className="pb-3">
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center space-x-2">
                                    <MessageCircle className="h-4 w-4 text-blue-600" />
                                    <CardTitle className="text-sm">{example.title}</CardTitle>
                                  </div>
                                  {example.hashtags && (
                                    <span className="text-xs text-gray-500">{example.hashtags}</span>
                                  )}
                                </div>
                              </CardHeader>
                              <CardContent className="pt-0">
                                <p className="text-xs text-gray-600 whitespace-pre-line">
                                  {example.example}
                                </p>
                              </CardContent>
                            </Card>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="mt-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                        <div className="flex items-center space-x-2">
                          <Lightbulb className="h-4 w-4 text-yellow-600" />
                          <span className="text-sm text-yellow-800">
                            성격을 입력하고 '말투 생성' 버튼을 누르면 추천 말투가 생성됩니다.
                          </span>
                        </div>
                      </div>
                    )}
                  </TabsContent>
                  <TabsContent value="custom">
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 mb-1">
                        <Lightbulb className="h-4 w-4 text-yellow-600" />
                        <span className="text-sm text-yellow-800">
                          캐릭터의 실제 대사를 7개 이상 입력해주세요. ({formData.customTones.length}/7개)
                        </span>
                      </div>
                      {formData.customTones.length < 7 && (
                        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg mb-2">
                          <p className="text-sm text-blue-700">
                            💡 캐릭터가 실제로 할 법한 대사를 입력하세요. 예:
                            <br />• "안녕! 오늘도 좋은 하루 보내고 있어?"
                            <br />• "우와, 이거 정말 대박이다!"
                            <br />• "음... 그건 좀 어려운 문제네요."
                          </p>
                        </div>
                      )}
                      <div className="flex gap-2">
                        <Input
                          value={customToneInput}
                          onChange={e => setCustomToneInput(e.target.value)}
                          placeholder="캐릭터의 대사를 입력하세요"
                          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAddCustomTone(); } }}
                        />
                        <Button type="button" onClick={handleAddCustomTone} disabled={!customToneInput.trim()}>
                          추가
                        </Button>
                      </div>
                      <ul className="space-y-1">
                        {generatedTones.length > 0 ? (
                          generatedTones.map((tone, idx) => (
                            <li key={idx} className="flex items-center gap-2 bg-gray-50 rounded px-3 py-2">
                              <span className="flex-1 text-sm">{tone.title} - {tone.tone}</span>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  setFormData(prev => ({
                                    ...prev,
                                    customTones: [tone.tone]
                                  }))
                                }}
                              >
                                선택
                              </Button>
                            </li>
                          ))
                        ) : formData.customTones && formData.customTones.length > 0 ? (
                          formData.customTones.map((tone, idx) => (
                            <li key={idx} className="flex items-center gap-2 bg-gray-50 rounded px-3 py-2">
                              <span className="flex-1 text-sm">{tone}</span>
                              <Button type="button" size="icon" variant="ghost" onClick={() => handleRemoveCustomTone(idx)}>
                                <Trash2 className="w-4 h-4 text-red-500" />
                              </Button>
                            </li>
                          ))
                        ) : (
                          <li className="text-gray-400 text-sm">아직 추가된 말투가 없습니다.</li>
                        )}
                      </ul>
                    </div>
                  </TabsContent>
                </Tabs>
              </div>
            </CardContent>
          </Card>

          {/* 이미지 업로드/생성 카드 */}
          <Card>
            <CardHeader>
              <CardTitle>이미지 설정</CardTitle>
              <CardDescription>
                AI 인플루언서의 이미지를 업로드하세요.<br />
                이미지 업로드는 필수입니다.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* 이미지 업로드 섹션 */}
              <div>
                    <div>
                      <Label className="text-base font-medium mb-3 block">이미지 파일 업로드</Label>
                      
                      {imagePreviewUrls.length === 0 ? (
                        // 이미지가 없을 때: 업로드 영역 표시
                        <div className="relative group transition-all duration-300 hover:scale-[1.02]">
                          <div className="relative overflow-hidden rounded-xl border-2 border-dashed transition-all duration-300 border-gray-300 bg-gradient-to-br from-gray-50 to-white hover:border-blue-400 hover:bg-gradient-to-br hover:from-blue-50 hover:to-indigo-50">
                            {/* 배경 패턴 */}
                            <div className="absolute inset-0 opacity-5">
                              <div className="absolute top-4 left-4 w-8 h-8 border-2 border-gray-400 rounded-lg"></div>
                              <div className="absolute top-12 right-8 w-6 h-6 border-2 border-gray-400 rounded-full"></div>
                              <div className="absolute bottom-8 left-12 w-4 h-4 border-2 border-gray-400 rotate-45"></div>
                              <div className="absolute bottom-16 right-4 w-10 h-10 border-2 border-gray-400 rounded-lg"></div>
                            </div>

                            <div className="relative p-12 text-center">
                              {/* 아이콘 영역 */}
                              <div className="relative mx-auto mb-6 w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 bg-gray-100 group-hover:bg-blue-100 group-hover:shadow-lg group-hover:shadow-blue-200">
                                <Upload className="h-8 w-8 transition-all duration-300 text-gray-500 group-hover:text-blue-600 group-hover:scale-110" />
                              </div>

                              {/* 텍스트 영역 */}
                              <div className="space-y-3">
                                <h3 className="text-xl font-semibold transition-colors duration-300 text-gray-800 group-hover:text-blue-700">
                                  이미지 업로드
                                </h3>
                                <p className="text-sm transition-colors duration-300 max-w-md mx-auto text-gray-600 group-hover:text-blue-600">
                                  AI 인플루언서 학습용 이미지들을 드래그하여 놓거나 클릭하여 선택하세요
                                </p>
                                <p className="text-xs text-gray-500">
                                  지원 형식: JPG, PNG, WebP (여러 파일 선택 가능)
                                </p>
                              </div>

                              {/* 파일 선택 버튼 */}
                              <div className="mt-6">
                                <input
                                  type="file"
                                  multiple
                                  accept=".jpg,.jpeg,.png,.webp"
                                  onChange={(e) => handleFileUpload("imageSamples", e.target.files)}
                                  className="hidden"
                                  id="image-upload"
                                />
                                <label htmlFor="image-upload">
                                  <Button
                                    className="transition-all duration-300 cursor-pointer bg-white hover:bg-blue-50 text-gray-700 border-gray-300 hover:border-blue-400 hover:text-blue-700 shadow-sm hover:shadow-md"
                                    asChild
                                  >
                                    <span className="flex items-center gap-2">
                                      <Upload className="h-4 w-4" />
                                      파일 선택
                                    </span>
                                  </Button>
                                </label>
                              </div>
                            </div>
                          </div>
                        </div>
                      ) : (
                        // 이미지가 있을 때: 미리보기와 추가 업로드 버튼
                        <div className="space-y-6">
                          {/* 업로드된 이미지 미리보기 */}
                          <div>
                            <div className="flex items-center justify-between mb-4">
                              <Label className="text-base font-medium">프로필 이미지</Label>
                              <div className="flex gap-2">
                                <input
                                  type="file"
                                  multiple
                                  accept=".jpg,.jpeg,.png,.webp"
                                  onChange={(e) => handleFileUpload("imageSamples", e.target.files)}
                                  className="hidden"
                                  id="image-upload-additional"
                                />
                                <label htmlFor="image-upload-additional">
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    className="cursor-pointer"
                                    asChild
                                  >
                                    <span className="flex items-center gap-2">
                                      <Upload className="h-4 w-4" />
                                      이미지 변경
                                    </span>
                                  </Button>
                                </label>
                              </div>
                            </div>
                            
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                              {imagePreviewUrls.map((url, index) => (
                                <div key={index} className="relative group">
                                  <div className="aspect-square rounded-lg overflow-hidden border-2 border-gray-200 hover:border-blue-400 transition-colors">
                                    <img
                                      src={url}
                                      alt={`미리보기 ${index + 1}`}
                                      className="w-full h-full object-cover"
                                    />
                                  </div>
                                  <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                <Button
                                  type="button"
                                  size="icon"
                                  variant="destructive"
                                  className="h-6 w-6"
                                  onClick={() => {
                                    // 해당 이미지 제거
                                    const newFiles = files.imageSamples?.filter((_, i) => i !== index) || []
                                    const newUrls = imagePreviewUrls.filter((_, i) => i !== index)
                                    setFiles(prev => ({ ...prev, imageSamples: newFiles.length > 0 ? newFiles : null }))
                                    setImagePreviewUrls(newUrls)
                                    // 기존 URL 해제
                                    URL.revokeObjectURL(url)
                                  }}
                                >
                                  <Trash2 className="h-3 w-3" />
                                </Button>
                                  </div>
                                  <p className="text-xs text-gray-500 mt-1 text-center truncate">
                                    {files.imageSamples?.[index]?.name || `이미지 ${index + 1}`}
                                  </p>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end gap-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => router.push("/dashboard")}
              disabled={isLoading}
            >
              취소
            </Button>
            <Button 
              type="submit" 
              disabled={
                isLoading || 
                !formData.name.trim() || // 이름*
                !formData.description.trim() || // 설명*
                formData.gender === "none" || !formData.gender || // 성별*
                formData.huggingFaceToken === "none" || !formData.huggingFaceToken || // 허깅페이스 토큰*
                !formData.personality.trim() || // 성격*
                // 말투 검증: 추천 말투 탭에서는 tone 필수, 대사 입력 탭에서는 7개 이상 필수
                (toneTab === "recommend" ? !formData.tone.trim() : formData.customTones.length < 7) ||
                // 이미지 업로드 필수
                (!files.imageSamples || files.imageSamples.length === 0)
              } 
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              {isLoading ? '생성 중...' : '생성하기'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}