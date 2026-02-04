import { Injectable, Logger } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import OpenAI from "openai";
import {
  ChatCompletionMessageParam,
  ChatCompletionToolMessageParam,
} from "openai/resources/chat/completions";
import { locomotiveTools } from "./tools/locomotive.tools";
import { ToolExecutorService } from "./services/tool-executor.service";
import { SYSTEM_PROMPT } from "./prompts/system.prompt";

export interface IntentAnalysis {
  intent: string;
  expectedTools: string[];
  steps: Array<{
    id: string;
    text: string;
    toolName?: string;
  }>;
}

export interface AiResponse {
  content: string;
  metadata?: {
    toolsUsed?: string[];
    processingTime?: number;
    intentAnalysis?: IntentAnalysis;
  };
}

@Injectable()
export class AiService {
  private readonly logger = new Logger(AiService.name);
  private readonly openai: OpenAI;
  private readonly model: string;

  constructor(
    private readonly configService: ConfigService,
    private readonly toolExecutor: ToolExecutorService,
  ) {
    this.openai = new OpenAI({
      apiKey: this.configService.get<string>("OPENAI_API_KEY"),
    });
    this.model =
      this.configService.get<string>("OPENAI_MODEL") || "gpt-4o-mini";
  }

  // Tool labels for UI display
  private readonly toolLabels: Record<string, string> = {
    get_total_locomotives_count: "Lokomotivlar sonini olish",
    get_locomotives_by_state: "Holat bo'yicha ma'lumotlar",
    get_stats: "Statistika yuklanmoqda",
    get_locomotive_types: "Lokomotiv turlari tekshirilmoqda",
    get_locomotive_models: "Model ma'lumotlari olinmoqda",
    get_active_repairs: "Faol ta'mirlar tekshirilmoqda",
    get_locomotive_last_repair: "Ta'mir tarixini olish",
    get_all_last_repairs: "Barcha ta'mirlar yuklanmoqda",
    search_locomotive_by_name: "Lokomotiv qidirilmoqda",
    get_locomotive_detailed_info: "Batafsil ma'lumot olinmoqda",
    get_current_inspections: "Joriy tekshiruvlar",
    get_total_inspection_counts: "Tekshiruv statistikasi",
    get_depo_info: "Depo ma'lumotlari olinmoqda",
    get_all_depos_info: "Barcha depolar tekshirilmoqda",
    get_repair_stats_by_year: "Yillik statistika yuklanmoqda",
  };

  // Analyze user intent and predict which tools will be used
  analyzeIntent(userMessage: string): IntentAnalysis {
    const message = userMessage.toLowerCase();
    const expectedTools: string[] = [];
    const steps: Array<{ id: string; text: string; toolName?: string }> = [];

    // Add analysis step first
    steps.push({
      id: "analyze",
      text: "So'rovni tahlil qilish",
    });

    // Context-aware location queries - check for locomotive numbers in message
    const locomotiveMatch = userMessage.match(/\b\d{3,4}\b/);
    const isLocationQuery =
      message.includes("qayerda") ||
      message.includes("joylashuv") ||
      message.includes("hozir qayerda") ||
      message.includes("qaysi joy") ||
      message.includes("hozir");

    if (isLocationQuery && locomotiveMatch) {
      expectedTools.push("search_locomotive_by_name");
      steps.push({
        id: "location_search",
        text: `${locomotiveMatch[0]} lokomotivning joylashuvini aniqlayman`,
        toolName: "search_locomotive_by_name",
      });
    } else if (isLocationQuery && !locomotiveMatch) {
      // If asking location but no number, look for locomotive references in context
      expectedTools.push("search_locomotive_by_name");
      steps.push({
        id: "context_search",
        text: "Oldingi suhbatdagi lokomotiv joylashuvini aniqlayman",
        toolName: "search_locomotive_by_name",
      });
    }

    // Detect intent patterns
    if (
      message.includes("nechta") ||
      message.includes("soni") ||
      message.includes("jami")
    ) {
      if (message.includes("lokomotiv")) {
        expectedTools.push("get_total_locomotives_count");
      }
      if (message.includes("tekshiruv") || message.includes("inspeksiya")) {
        expectedTools.push("get_total_inspection_counts");
      }
    }

    if (
      message.includes("holat") ||
      message.includes("ishlamoqda") ||
      message.includes("ta'mirda")
    ) {
      expectedTools.push("get_locomotives_by_state");
    }

    if (message.includes("statistika") || message.includes("hisobot")) {
      expectedTools.push("get_stats");
      if (message.includes("yil")) {
        expectedTools.push("get_repair_stats_by_year");
      }
    }

    if (message.includes("tur") && message.includes("lokomotiv")) {
      expectedTools.push("get_locomotive_types");
    }

    if (message.includes("model")) {
      expectedTools.push("get_locomotive_models");
    }

    if (
      message.includes("ta'mir") &&
      (message.includes("faol") || message.includes("hozirgi"))
    ) {
      expectedTools.push("get_active_repairs");
    }

    if (message.includes("ta'mir") && message.includes("oxirgi")) {
      if (message.includes("barcha") || message.includes("hamma")) {
        expectedTools.push("get_all_last_repairs");
      } else {
        expectedTools.push("get_locomotive_last_repair");
      }
    }

    if (
      message.includes("qidir") ||
      message.includes("top") ||
      message.includes("izla")
    ) {
      expectedTools.push("search_locomotive_by_name");
    }

    if (message.includes("batafsil") || message.includes("ma'lumot")) {
      expectedTools.push("get_locomotive_detailed_info");
    }

    if (message.includes("tekshiruv") && message.includes("hozir")) {
      expectedTools.push("get_current_inspections");
    }

    if (message.includes("depo")) {
      if (message.includes("barcha") || message.includes("hamma")) {
        expectedTools.push("get_all_depos_info");
      } else {
        expectedTools.push("get_depo_info");
      }
    }

    // Add tool execution steps
    expectedTools.forEach((toolName, index) => {
      steps.push({
        id: `tool_${index}`,
        text: this.toolLabels[toolName] || `${toolName} bajarilmoqda`,
        toolName,
      });
    });

    // If no specific tools detected, add generic data fetch step
    if (expectedTools.length === 0) {
      steps.push({
        id: "fetch",
        text: "Ma'lumotlar yuklanmoqda",
      });
    }

    // Add response generation step
    steps.push({
      id: "generate",
      text: "Javob tayyorlanmoqda",
    });

    return {
      intent: this.detectIntentCategory(message),
      expectedTools,
      steps,
    };
  }

  private detectIntentCategory(message: string): string {
    if (message.includes("qidir") || message.includes("top")) return "search";
    if (message.includes("statistika") || message.includes("hisobot"))
      return "statistics";
    if (message.includes("ta'mir")) return "repair";
    if (message.includes("tekshiruv")) return "inspection";
    if (message.includes("depo")) return "depot";
    if (message.includes("nechta") || message.includes("soni")) return "count";
    return "general";
  }

  async processMessage(
    userMessage: string,
    conversationHistory: Array<{ role: string; content: string }>,
  ): Promise<AiResponse> {
    const startTime = Date.now();
    const toolsUsed: string[] = [];

    // Analyze intent before processing
    const intentAnalysis = this.analyzeIntent(userMessage);
    this.logger.log(`Intent analysis: ${JSON.stringify(intentAnalysis)}`);

    // Extract locomotive number from context if needed
    const enhancedMessage = this.enhanceMessageWithContext(
      userMessage,
      conversationHistory,
    );
    const finalMessage = enhancedMessage || userMessage;

    try {
      const messages: ChatCompletionMessageParam[] = [
        { role: "system", content: SYSTEM_PROMPT },
        ...this.formatConversationHistory(conversationHistory),
        { role: "user", content: finalMessage },
      ];

      let response = await this.openai.chat.completions.create({
        model: this.model,
        messages,
        tools: locomotiveTools,
        tool_choice: "auto",
        temperature: 0.3,
        max_tokens: 2000,
      });

      let assistantMessage = response.choices[0].message;
      let iterationCount = 0;
      const maxIterations = 5;

      while (
        assistantMessage.tool_calls &&
        assistantMessage.tool_calls.length > 0 &&
        iterationCount < maxIterations
      ) {
        iterationCount++;
        this.logger.log(
          `Processing ${assistantMessage.tool_calls.length} tool calls (iteration ${iterationCount})`,
        );

        messages.push(assistantMessage);

        const toolResponses: ChatCompletionToolMessageParam[] = [];

        for (const toolCall of assistantMessage.tool_calls) {
          const functionName = toolCall.function.name;
          const functionArgs = JSON.parse(toolCall.function.arguments);

          this.logger.log(
            `Executing tool: ${functionName} with args: ${JSON.stringify(functionArgs)}`,
          );

          toolsUsed.push(functionName);

          const result = await this.toolExecutor.executeFunction(
            functionName,
            functionArgs,
          );

          toolResponses.push({
            role: "tool",
            tool_call_id: toolCall.id,
            content: JSON.stringify({
              success: result.success,
              data: result.data,
              summary: result.summary,
            }),
          });
        }

        messages.push(...toolResponses);

        response = await this.openai.chat.completions.create({
          model: this.model,
          messages,
          tools: locomotiveTools,
          tool_choice: "auto",
          temperature: 0.3,
          max_tokens: 2000,
        });

        assistantMessage = response.choices[0].message;
      }

      const processingTime = Date.now() - startTime;

      return {
        content: assistantMessage.content || "Javob olishda xatolik yuz berdi",
        metadata: {
          toolsUsed: toolsUsed.length > 0 ? toolsUsed : undefined,
          processingTime,
          intentAnalysis,
        },
      };
    } catch (error) {
      this.logger.error("AI processing error:", error);
      this.logger.error("Error message:", error.message);
      if (error.response) {
        this.logger.error("API Response:", error.response.data);
      }
      throw error;
    }
  }

  private enhanceMessageWithContext(
    userMessage: string,
    conversationHistory: Array<{ role: string; content: string }>,
  ): string | null {
    const message = userMessage.toLowerCase().trim();

    // Check if it's a context-dependent location query
    const isLocationQuery =
      message.includes("qayerda") ||
      message.includes("joylashuv") ||
      message.includes("hozir") ||
      message.includes("qaysi joy");

    if (!isLocationQuery) return null;

    // Look for locomotive numbers in recent conversation
    const recentMessages = conversationHistory.slice(-6); // Last 6 messages

    for (let i = recentMessages.length - 1; i >= 0; i--) {
      const msg = recentMessages[i];

      // Look for locomotive numbers in user messages and AI responses
      const locomotiveMatches = msg.content.match(
        /(?:UZ-EL\s*)?(\d{3,4})|lokomotiv[:\s]*(\d{3,4})/gi,
      );

      if (locomotiveMatches) {
        const numberMatch = locomotiveMatches[0].match(/\d{3,4}/);
        if (numberMatch) {
          const number = numberMatch[0];
          this.logger.log(
            `Found locomotive context: ${number} for query: ${userMessage}`,
          );
          return `${number} lokomotiv ${userMessage}`;
        }
      }
    }

    return null;
  }

  private formatConversationHistory(
    history: Array<{ role: string; content: string }>,
  ): ChatCompletionMessageParam[] {
    const recentHistory = history.slice(-10);

    return recentHistory.map((msg) => ({
      role: msg.role as "user" | "assistant",
      content: msg.content,
    }));
  }
}
