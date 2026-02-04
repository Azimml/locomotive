import { Module } from "@nestjs/common";
import { AiService } from "./ai.service";
import { ToolExecutorService } from "./services/tool-executor.service";
import { LocomotiveModule } from "../locomotive/locomotive.module";

@Module({
  imports: [LocomotiveModule],
  providers: [AiService, ToolExecutorService],
  exports: [AiService],
})
export class AiModule {}
