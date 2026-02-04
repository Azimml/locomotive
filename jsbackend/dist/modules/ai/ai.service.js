"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
var AiService_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.AiService = void 0;
const common_1 = require("@nestjs/common");
const config_1 = require("@nestjs/config");
const openai_1 = require("openai");
const locomotive_tools_1 = require("./tools/locomotive.tools");
const tool_executor_service_1 = require("./services/tool-executor.service");
const system_prompt_1 = require("./prompts/system.prompt");
let AiService = AiService_1 = class AiService {
    constructor(configService, toolExecutor) {
        this.configService = configService;
        this.toolExecutor = toolExecutor;
        this.logger = new common_1.Logger(AiService_1.name);
        this.toolLabels = {
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
        this.openai = new openai_1.default({
            apiKey: this.configService.get("OPENAI_API_KEY"),
        });
        this.model =
            this.configService.get("OPENAI_MODEL") || "gpt-4o-mini";
    }
    analyzeIntent(userMessage) {
        const message = userMessage.toLowerCase();
        const expectedTools = [];
        const steps = [];
        steps.push({
            id: "analyze",
            text: "So'rovni tahlil qilish",
        });
        const locomotiveMatch = userMessage.match(/\b\d{3,4}\b/);
        const isLocationQuery = message.includes("qayerda") ||
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
        }
        else if (isLocationQuery && !locomotiveMatch) {
            expectedTools.push("search_locomotive_by_name");
            steps.push({
                id: "context_search",
                text: "Oldingi suhbatdagi lokomotiv joylashuvini aniqlayman",
                toolName: "search_locomotive_by_name",
            });
        }
        if (message.includes("nechta") ||
            message.includes("soni") ||
            message.includes("jami")) {
            if (message.includes("lokomotiv")) {
                expectedTools.push("get_total_locomotives_count");
            }
            if (message.includes("tekshiruv") || message.includes("inspeksiya")) {
                expectedTools.push("get_total_inspection_counts");
            }
        }
        if (message.includes("holat") ||
            message.includes("ishlamoqda") ||
            message.includes("ta'mirda")) {
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
        if (message.includes("ta'mir") &&
            (message.includes("faol") || message.includes("hozirgi"))) {
            expectedTools.push("get_active_repairs");
        }
        if (message.includes("ta'mir") && message.includes("oxirgi")) {
            if (message.includes("barcha") || message.includes("hamma")) {
                expectedTools.push("get_all_last_repairs");
            }
            else {
                expectedTools.push("get_locomotive_last_repair");
            }
        }
        if (message.includes("qidir") ||
            message.includes("top") ||
            message.includes("izla")) {
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
            }
            else {
                expectedTools.push("get_depo_info");
            }
        }
        expectedTools.forEach((toolName, index) => {
            steps.push({
                id: `tool_${index}`,
                text: this.toolLabels[toolName] || `${toolName} bajarilmoqda`,
                toolName,
            });
        });
        if (expectedTools.length === 0) {
            steps.push({
                id: "fetch",
                text: "Ma'lumotlar yuklanmoqda",
            });
        }
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
    detectIntentCategory(message) {
        if (message.includes("qidir") || message.includes("top"))
            return "search";
        if (message.includes("statistika") || message.includes("hisobot"))
            return "statistics";
        if (message.includes("ta'mir"))
            return "repair";
        if (message.includes("tekshiruv"))
            return "inspection";
        if (message.includes("depo"))
            return "depot";
        if (message.includes("nechta") || message.includes("soni"))
            return "count";
        return "general";
    }
    async processMessage(userMessage, conversationHistory) {
        const startTime = Date.now();
        const toolsUsed = [];
        const intentAnalysis = this.analyzeIntent(userMessage);
        this.logger.log(`Intent analysis: ${JSON.stringify(intentAnalysis)}`);
        const enhancedMessage = this.enhanceMessageWithContext(userMessage, conversationHistory);
        const finalMessage = enhancedMessage || userMessage;
        try {
            const messages = [
                { role: "system", content: system_prompt_1.SYSTEM_PROMPT },
                ...this.formatConversationHistory(conversationHistory),
                { role: "user", content: finalMessage },
            ];
            let response = await this.openai.chat.completions.create({
                model: this.model,
                messages,
                tools: locomotive_tools_1.locomotiveTools,
                tool_choice: "auto",
                temperature: 0.3,
                max_tokens: 2000,
            });
            let assistantMessage = response.choices[0].message;
            let iterationCount = 0;
            const maxIterations = 5;
            while (assistantMessage.tool_calls &&
                assistantMessage.tool_calls.length > 0 &&
                iterationCount < maxIterations) {
                iterationCount++;
                this.logger.log(`Processing ${assistantMessage.tool_calls.length} tool calls (iteration ${iterationCount})`);
                messages.push(assistantMessage);
                const toolResponses = [];
                for (const toolCall of assistantMessage.tool_calls) {
                    const functionName = toolCall.function.name;
                    const functionArgs = JSON.parse(toolCall.function.arguments);
                    this.logger.log(`Executing tool: ${functionName} with args: ${JSON.stringify(functionArgs)}`);
                    toolsUsed.push(functionName);
                    const result = await this.toolExecutor.executeFunction(functionName, functionArgs);
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
                    tools: locomotive_tools_1.locomotiveTools,
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
        }
        catch (error) {
            this.logger.error("AI processing error:", error);
            this.logger.error("Error message:", error.message);
            if (error.response) {
                this.logger.error("API Response:", error.response.data);
            }
            throw error;
        }
    }
    enhanceMessageWithContext(userMessage, conversationHistory) {
        const message = userMessage.toLowerCase().trim();
        const isLocationQuery = message.includes("qayerda") ||
            message.includes("joylashuv") ||
            message.includes("hozir") ||
            message.includes("qaysi joy");
        if (!isLocationQuery)
            return null;
        const recentMessages = conversationHistory.slice(-6);
        for (let i = recentMessages.length - 1; i >= 0; i--) {
            const msg = recentMessages[i];
            const locomotiveMatches = msg.content.match(/(?:UZ-EL\s*)?(\d{3,4})|lokomotiv[:\s]*(\d{3,4})/gi);
            if (locomotiveMatches) {
                const numberMatch = locomotiveMatches[0].match(/\d{3,4}/);
                if (numberMatch) {
                    const number = numberMatch[0];
                    this.logger.log(`Found locomotive context: ${number} for query: ${userMessage}`);
                    return `${number} lokomotiv ${userMessage}`;
                }
            }
        }
        return null;
    }
    formatConversationHistory(history) {
        const recentHistory = history.slice(-10);
        return recentHistory.map((msg) => ({
            role: msg.role,
            content: msg.content,
        }));
    }
};
exports.AiService = AiService;
exports.AiService = AiService = AiService_1 = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [config_1.ConfigService,
        tool_executor_service_1.ToolExecutorService])
], AiService);
//# sourceMappingURL=ai.service.js.map