import { Injectable, UnauthorizedException } from "@nestjs/common";
import { JwtService } from "@nestjs/jwt";
import { UsersService } from "../users/users.service";
import { LoginDto } from "./dto/login.dto";

export interface JwtPayload {
  sub: string;
  login: string;
}

export interface AuthResponse {
  accessToken: string;
  user: {
    id: string;
    login: string;
    fullName: string | null;
  };
}

@Injectable()
export class AuthService {
  constructor(
    private readonly usersService: UsersService,
    private readonly jwtService: JwtService,
  ) {}

  async login(loginDto: LoginDto): Promise<AuthResponse> {
    const user = await this.usersService.findByLogin(loginDto.login);

    if (!user) {
      throw new UnauthorizedException("Login yoki parol noto'g'ri");
    }

    const isPasswordValid = await this.usersService.validatePassword(
      user,
      loginDto.password,
    );

    if (!isPasswordValid) {
      throw new UnauthorizedException("Login yoki parol noto'g'ri");
    }

    if (!user.isActive) {
      throw new UnauthorizedException("Foydalanuvchi faol emas");
    }

    const payload: JwtPayload = { sub: user.id, login: user.login };
    const accessToken = this.jwtService.sign(payload);

    return {
      accessToken,
      user: {
        id: user.id,
        login: user.login,
        fullName: user.fullName,
      },
    };
  }

  async validateUser(payload: JwtPayload) {
    return this.usersService.findById(payload.sub);
  }
}
