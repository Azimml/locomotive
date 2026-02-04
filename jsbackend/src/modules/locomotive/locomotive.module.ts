import { Module } from "@nestjs/common";
import { LocomotiveApiService } from "./locomotive-api.service";

@Module({
  providers: [LocomotiveApiService],
  exports: [LocomotiveApiService],
})
export class LocomotiveModule {}
