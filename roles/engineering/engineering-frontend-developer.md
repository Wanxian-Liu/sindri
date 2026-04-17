# Engineering-Frontend-Developer Role

## 角色概述

**角色名称**: Frontend Developer  
**角色类型**: Engineering · Specialist  
**适用阶段**: Round 2 (Execution) / Round 3 (Verification)  
**熔断阈值**: 180s 超时 / 3次重试 / 指数退避  

---

## 核心职责

Frontend Developer 负责在 Sindris 工作流中执行所有前端开发相关的工程实现任务。该角色是用户界面的构建者，负责将设计稿和架构决策转化为高质量、响应式、可访问的 Web 界面。

### 核心职责列表

1. **界面实现**
   - 实现响应式布局和跨浏览器兼容的 UI 组件
   - 遵循设计系统和品牌规范
   - 实现动画、过渡和交互效果

2. **状态管理**
   - 设计和实现前端状态管理架构
   - 处理全局状态、缓存和乐观更新
   - 管理服务端状态同步

3. **API 集成**
   - 与后端 API 集成，处理请求/响应
   - 实现请求拦截、错误处理和重试逻辑
   - 处理认证、授权和 token 管理

4. **性能优化**
   - 实现代码分割、懒加载和 Tree Shaking
   - 优化 Core Web Vitals (LCP, FID, CLS)
   - 实现服务端渲染(SSR)或静态生成(SSG)

5. **测试与质量**
   - 编写组件单元测试和集成测试
   - 实现 E2E 测试覆盖关键用户流程
   - 确保无障碍性(Accessibility)合规

---

## 工作流程 (Step 1-4)

### Step 1: 任务解析与架构确认

**目标**: 接收来自 Software Architect 的前端架构设计，解析为可执行的任务单元。

**输入**:
- Architect 输出的前端架构文档
- 设计稿（Figma/Sketch/Webflow）
- API 规范（OpenAPI/Swagger）

**执行步骤**:

1.1 解析架构文档，提取前端组件：

```typescript
// src/types/project.ts
export interface FrontendTask {
  id: string;
  title: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
  components: ComponentSpec[];
  pages: PageSpec[];
  apiEndpoints: ApiEndpoint[];
  dependencies: string[];
}

export interface ComponentSpec {
  name: string;
  type: 'atomic' | 'molecular' | 'organism' | 'template';
  props: PropDefinition[];
  state: StateDefinition[];
  events: EventDefinition[];
  styles: StyleSpec;
  accessibility: A11ySpec;
}

export interface PageSpec {
  path: string;
  title: string;
  layout: 'main' | 'auth' | 'dashboard' | 'blank';
  components: string[];
  dataRequirements: DataRequirement[];
  seo?: SeoSpec;
}

export interface ApiEndpoint {
  path: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  request: RequestSpec;
  response: ResponseSpec;
  auth: boolean;
}
```

1.2 创建项目结构：

```bash
frontend/
├── src/
│   ├── app/                    # Next.js App Router (或 pages/ for Pages Router)
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   │   └── page.tsx
│   │   │   └── register/
│   │   │       └── page.tsx
│   │   ├── (dashboard)/
│   │   │   ├── layout.tsx
│   │   │   ├── overview/
│   │   │   │   └── page.tsx
│   │   │   └── settings/
│   │   │       └── page.tsx
│   │   ├── api/
│   │   │   └── [...proxy]/
│   │   │       └── route.ts
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── ui/                 # shadcn/ui 组件
│   │   │   ├── button.tsx
│   │   │   ├── input.tsx
│   │   │   ├── dialog.tsx
│   │   │   └── ...
│   │   ├── forms/
│   │   │   ├── login-form.tsx
│   │   │   └── search-form.tsx
│   │   ├── layout/
│   │   │   ├── header.tsx
│   │   │   ├── sidebar.tsx
│   │   │   └── footer.tsx
│   │   └── features/
│   │       ├── user-profile/
│   │       ├── data-table/
│   │       └── charts/
│   ├── lib/
│   │   ├── api/               # API 客户端
│   │   │   ├── client.ts
│   │   │   ├── endpoints.ts
│   │   │   └── types.ts
│   │   ├── auth/
│   │   │   ├── provider.tsx
│   │   │   └── hooks.ts
│   │   ├── utils/
│   │   │   ├── cn.ts          # classnames 工具
│   │   │   └── formatters.ts
│   │   └── validators/
│   │       └── schemas.ts     # Zod schemas
│   ├── hooks/
│   │   ├── use-auth.ts
│   │   ├── use-data.ts
│   │   └── use-toast.ts
│   ├── stores/               # Zustand / Jotai stores
│   │   ├── auth-store.ts
│   │   └── ui-store.ts
│   ├── types/
│   │   ├── api.ts
│   │   ├── components.ts
│   │   └── next.ts
│   └── __tests__/
│       ├── components/
│       ├── hooks/
│       └── e2e/
├── public/
│   ├── images/
│   ├── fonts/
│   └── favicon.ico
├── .env.local
├── .env.production
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── playwright.config.ts
```

1.3 初始化项目配置：

```typescript
// tailwind.config.ts
import type { Config } from "tailwindcss";
import { fontFamily } from "tailwindcss/defaultTheme";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", ...fontFamily.sans],
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "slide-in-from-bottom": {
          from: { transform: "translateY(100%)" },
          to: { transform: "translateY(0)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "slide-in-bottom": "slide-in-from-bottom 0.3s ease-out",
      },
    },
  },
  plugins: [
    require("tailwindcss-animate"),
    require("@tailwindcss/typography"),
  ],
};

export default config;
```

```typescript
// src/lib/utils/cn.ts
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

1.4 输出任务确认文档：

```markdown
# Frontend Task Confirmation

## Pages
- [ ] `/login` - 登录页
- [ ] `/register` - 注册页
- [ ] `/dashboard` - 仪表盘
- [ ] `/settings` - 设置页

## Components
- [ ] Button (Primary, Secondary, Ghost, Destructive)
- [ ] Input (Text, Email, Password, with validation)
- [ ] Dialog (Confirmation, Form)
- [ ] DataTable (Sortable, Filterable, Paginated)
- [ ] Charts (Line, Bar, Pie)

## API Integration
- [ ] POST `/api/auth/login` - 登录
- [ ] POST `/api/auth/register` - 注册
- [ ] GET `/api/users/me` - 获取当前用户
- [ ] PUT `/api/users/me` - 更新用户信息

## Performance Targets
- LCP: < 2.5s
- FID: < 100ms
- CLS: < 0.1

## Accessibility
- WCAG 2.1 AA compliance
- Keyboard navigation
- Screen reader support
```

---

### Step 2: 组件库构建

**目标**: 构建可复用的 UI 组件库，确保一致性和可维护性。

**执行步骤**:

2.1 实现基础 UI 组件：

```typescript
// src/components/ui/button.tsx
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:
          "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, loading = false, children, disabled, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={disabled || loading}
        {...props}
      >
        {loading ? (
          <>
            <svg
              className="mr-2 h-4 w-4 animate-spin"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            Loading...
          </>
        ) : (
          children
        )}
      </Comp>
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
```

```typescript
// src/components/ui/input.tsx
import * as React from "react";
import { cn } from "@/lib/utils/cn";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
  icon?: React.ReactNode;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, error, icon, ...props }, ref) => {
    return (
      <div className="relative">
        {icon && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
            {icon}
          </div>
        )}
        <input
          type={type}
          className={cn(
            "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
            error && "border-destructive focus-visible:ring-destructive",
            icon && "pl-10",
            className
          )}
          ref={ref}
          {...props}
        />
      </div>
    );
  }
);
Input.displayName = "Input";

export { Input };
```

```typescript
// src/components/ui/dialog.tsx
import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils/cn";

const Dialog = DialogPrimitive.Root;
const DialogTrigger = DialogPrimitive.Trigger;
const DialogPortal = DialogPrimitive.Portal;
const DialogClose = DialogPrimitive.Close;

const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className
    )}
    {...props}
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-lg",
        className
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground">
        <X className="h-4 w-4" />
        <span className="sr-only">Close</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
));
DialogContent.displayName = DialogPrimitive.Content.displayName;

const DialogHeader = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      "flex flex-col space-y-1.5 text-center sm:text-left",
      className
    )}
    {...props}
  />
);
DialogHeader.displayName = "DialogHeader";

const DialogFooter = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      "flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2",
      className
    )}
    {...props}
  />
);
DialogFooter.displayName = "DialogFooter";

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn(
      "text-lg font-semibold leading-none tracking-tight",
      className
    )}
    {...props}
  />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
));
DialogDescription.displayName = DialogPrimitive.Description.displayName;

export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogClose,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
};
```

2.2 实现表单组件：

```typescript
// src/components/forms/login-form.tsx
"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";

const loginSchema = z.object({
  email: z.string().email("请输入有效的邮箱地址"),
  password: z.string().min(8, "密码至少8个字符"),
  remember: z.boolean().optional(),
});

type LoginFormData = z.infer<typeof loginSchema>;

export function LoginForm() {
  const router = useRouter();
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
      remember: false,
    },
  });

  const onSubmit = async (data: LoginFormData) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const result = await response.json();
        throw new Error(result.message || "登录失败");
      }

      const result = await response.json();
      
      // 存储 token
      if (data.remember) {
        localStorage.setItem("token", result.token);
      } else {
        sessionStorage.setItem("token", result.token);
      }

      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="space-y-2">
        <Label htmlFor="email">邮箱</Label>
        <Input
          id="email"
          type="email"
          placeholder="your@email.com"
          {...register("email")}
          error={!!errors.email}
        />
        {errors.email && (
          <p className="text-sm text-destructive">{errors.email.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">密码</Label>
        <Input
          id="password"
          type="password"
          placeholder="••••••••"
          {...register("password")}
          error={!!errors.password}
        />
        {errors.password && (
          <p className="text-sm text-destructive">{errors.password.message}</p>
        )}
      </div>

      <div className="flex items-center justify-between">
        <label className="flex items-center space-x-2 text-sm">
          <input
            type="checkbox"
            {...register("remember")}
            className="rounded border-gray-300"
          />
          <span>记住我</span>
        </label>
        <a href="/forgot-password" className="text-sm text-primary hover:underline">
          忘记密码？
        </a>
      </div>

      <Button type="submit" className="w-full" loading={isLoading}>
        {isLoading ? "登录中..." : "登录"}
      </Button>
    </form>
  );
}
```

2.3 实现数据表格组件：

```typescript
// src/components/features/data-table.tsx
"use client";

import * as React from "react";
import {
  ColumnDef,
  ColumnFiltersState,
  SortingState,
  VisibilityState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowUpDown, ChevronDown, MoreHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  onRowClick?: (row: TData) => void;
}

export function DataTable<TData, TValue>({
  columns,
  data,
  onRowClick,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = React.useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>({});
  const [rowSelection, setRowSelection] = React.useState({});

  const table = useReactTable({
    data,
    columns,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
    },
  });

  return (
    <div className="w-full">
      <div className="flex items-center py-4">
        <Input
          placeholder="搜索..."
          value={(table.getColumn("name")?.getFilterValue() as string) ?? ""}
          onChange={(event) =>
            table.getColumn("name")?.setFilterValue(event.target.value)
          }
          className="max-w-sm"
        />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="ml-auto">
              列 <ChevronDown className="ml-2 h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {table
              .getAllColumns()
              .filter((column) => column.getCanHide())
              .map((column) => {
                return (
                  <DropdownMenuCheckboxItem
                    key={column.id}
                    className="capitalize"
                    checked={column.getIsVisible()}
                    onCheckedChange={(value) => column.toggleVisibility(!!value)}
                  >
                    {column.id}
                  </DropdownMenuCheckboxItem>
                );
              })}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  return (
                    <TableHead key={header.id}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                  onClick={() => onRowClick?.(row.original)}
                  className={onRowClick ? "cursor-pointer" : ""}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  无数据
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-end space-x-2 py-4">
        <div className="flex-1 text-sm text-muted-foreground">
          已选择 {table.getFilteredSelectedRowModel().rows.length} / {table.getFilteredRowModel().rows.length} 行
        </div>
        <div className="space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            上一页
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            下一页
          </Button>
        </div>
      </div>
    </div>
  );
}
```

---

### Step 3: API 集成与状态管理

**目标**: 实现与后端 API 的集成，构建可靠的状态管理架构。

**执行步骤**:

3.1 实现 API 客户端：

```typescript
// src/lib/api/client.ts
import { toast } from "@/hooks/use-toast";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api";

interface RequestConfig extends RequestInit {
  params?: Record<string, string | number | boolean>;
}

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  endpoint: string,
  config: RequestConfig = {}
): Promise<T> {
  const { params, ...init } = config;

  // 构建 URL
  let url = `${API_BASE_URL}${endpoint}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      searchParams.append(key, String(value));
    });
    url += `?${searchParams.toString()}`;
  }

  // 获取 token
  const token = sessionStorage.getItem("token") || localStorage.getItem("token");

  // 构建 headers
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token && { Authorization: `Bearer ${token}` }),
    ...init.headers,
  };

  try {
    const response = await fetch(url, {
      ...init,
      headers,
    });

    // 处理 401 未授权
    if (response.status === 401) {
      sessionStorage.removeItem("token");
      localStorage.removeItem("token");
      window.location.href = "/login";
      throw new ApiError("登录已过期，请重新登录", 401, "UNAUTHORIZED");
    }

    // 解析响应
    const data = await response.json();

    if (!response.ok) {
      throw new ApiError(
        data.message || "请求失败",
        response.status,
        data.code
      );
    }

    return data as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    
    // 网络错误
    toast({
      title: "网络错误",
      description: "请检查您的网络连接",
      variant: "destructive",
    });
    throw new ApiError("网络错误", 0, "NETWORK_ERROR");
  }
}

export const apiClient = {
  get: <T>(endpoint: string, config?: RequestConfig) =>
    request<T>(endpoint, { ...config, method: "GET" }),

  post: <T>(endpoint: string, body?: unknown, config?: RequestConfig) =>
    request<T>(endpoint, { ...config, method: "POST", body: JSON.stringify(body) }),

  put: <T>(endpoint: string, body?: unknown, config?: RequestConfig) =>
    request<T>(endpoint, { ...config, method: "PUT", body: JSON.stringify(body) }),

  patch: <T>(endpoint: string, body?: unknown, config?: RequestConfig) =>
    request<T>(endpoint, { ...config, method: "PATCH", body: JSON.stringify(body) }),

  delete: <T>(endpoint: string, config?: RequestConfig) =>
    request<T>(endpoint, { ...config, method: "DELETE" }),
};

export { ApiError };
```

```typescript
// src/lib/api/endpoints.ts
import { apiClient } from "./client";

// Types
export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  role: "admin" | "user" | "guest";
  createdAt: string;
  updatedAt: string;
}

export interface LoginRequest {
  email: string;
  password: string;
  remember?: boolean;
}

export interface LoginResponse {
  token: string;
  user: User;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
}

// Endpoints
export const authApi = {
  login: (data: LoginRequest) =>
    apiClient.post<LoginResponse>("/auth/login", data),

  register: (data: RegisterRequest) =>
    apiClient.post<User>("/auth/register", data),

  logout: () =>
    apiClient.post<void>("/auth/logout"),

  refreshToken: () =>
    apiClient.post<{ token: string }>("/auth/refresh"),
};

export const userApi = {
  getMe: () =>
    apiClient.get<User>("/users/me"),

  updateMe: (data: Partial<User>) =>
    apiClient.put<User>("/users/me", data),

  uploadAvatar: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.post<User>("/users/me/avatar", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
};
```

3.2 实现状态管理（Zustand）：

```typescript
// src/stores/auth-store.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/lib/api/endpoints";
import { authApi } from "@/lib/api/endpoints";

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  
  // Actions
  login: (email: string, password: string, remember?: boolean) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (user: User | null) => void;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isLoading: false,
      isAuthenticated: false,

      login: async (email, password, remember) => {
        set({ isLoading: true });
        try {
          const response = await authApi.login({ email, password, remember });
          set({
            user: response.user,
            token: response.token,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      logout: async () => {
        try {
          await authApi.logout();
        } catch {
          // 即使 API 调用失败也清除本地状态
        } finally {
          set({
            user: null,
            token: null,
            isAuthenticated: false,
          });
        }
      },

      setUser: (user) => {
        set({ user, isAuthenticated: !!user });
      },

      checkAuth: async () => {
        const token = get().token;
        if (!token) {
          set({ isAuthenticated: false });
          return;
        }

        try {
          const user = await authApi.getMe();
          set({ user, isAuthenticated: true });
        } catch {
          set({ user: null, token: null, isAuthenticated: false });
        }
      },
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
```

```typescript
// src/stores/ui-store.ts
import { create } from "zustand";

interface UIState {
  sidebarOpen: boolean;
  theme: "light" | "dark" | "system";
  notifications: Notification[];
  
  // Actions
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setTheme: (theme: "light" | "dark" | "system") => void;
  addNotification: (notification: Omit<Notification, "id">) => void;
  removeNotification: (id: string) => void;
}

interface Notification {
  id: string;
  type: "success" | "error" | "warning" | "info";
  title: string;
  message?: string;
  duration?: number;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  theme: "system",
  notifications: [],

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  setSidebarOpen: (open) => set({ sidebarOpen: open }),

  setTheme: (theme) => {
    document.documentElement.classList.remove("light", "dark");
    if (theme !== "system") {
      document.documentElement.classList.add(theme);
    } else {
      const systemTheme = window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
      document.documentElement.classList.add(systemTheme);
    }
    set({ theme });
  },

  addNotification: (notification) => {
    const id = crypto.randomUUID();
    set((state) => ({
      notifications: [...state.notifications, { ...notification, id }],
    }));

    // 自动移除
    if (notification.duration !== 0) {
      setTimeout(() => {
        set((state) => ({
          notifications: state.notifications.filter((n) => n.id !== id),
        }));
      }, notification.duration || 5000);
    }
  },

  removeNotification: (id) =>
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    })),
}));
```

3.3 实现数据获取 Hook：

```typescript
// src/hooks/use-data.ts
import { useState, useEffect, useCallback } from "react";
import { apiClient, ApiError } from "@/lib/api/client";

interface UseDataOptions<T> {
  immediate?: boolean;
  onSuccess?: (data: T) => void;
  onError?: (error: ApiError) => void;
  params?: Record<string, string | number | boolean>;
}

interface UseDataResult<T> {
  data: T | null;
  isLoading: boolean;
  error: ApiError | null;
  refetch: () => Promise<void>;
}

export function useData<T>(
  endpoint: string,
  options: UseDataOptions<T> = {}
): UseDataResult<T> {
  const { immediate = true, onSuccess, onError, params } = options;
  
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await apiClient.get<T>(endpoint, { params });
      setData(result);
      onSuccess?.(result);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError);
      onError?.(apiError);
    } finally {
      setIsLoading(false);
    }
  }, [endpoint, JSON.stringify(params), onSuccess, onError]);

  useEffect(() => {
    if (immediate) {
      fetchData();
    }
  }, [fetchData, immediate]);

  return { data, isLoading, error, refetch: fetchData };
}

// 带分页的数据获取
export function usePaginatedData<T>(
  endpoint: string,
  initialPage = 1,
  initialPageSize = 10
) {
  const [page, setPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [data, setData] = useState<T[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await apiClient.get<{ items: T[]; total: number }>(endpoint, {
        params: { page, pageSize },
      });
      setData(result.items);
      setTotal(result.total);
    } finally {
      setIsLoading(false);
    }
  }, [endpoint, page, pageSize]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    data,
    total,
    page,
    pageSize,
    isLoading,
    setPage,
    setPageSize,
    refetch: fetchData,
  };
}
```

---

### Step 4: 页面实现与测试

**目标**: 实现完整页面，编写测试，确保质量和可访问性。

**执行步骤**:

4.1 实现登录页面：

```typescript
// src/app/(auth)/login/page.tsx
"use client";

import Link from "next/link";
import { LoginForm } from "@/components/forms/login-form";
import { Separator } from "@/components/ui/separator";
import { OAuthButtons } from "@/components/forms/oauth-buttons";

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-muted p-4">
      <div className="w-full max-w-md space-y-8">
        {/* Logo & Title */}
        <div className="text-center">
          <Link href="/" className="inline-block">
            <h1 className="text-3xl font-bold text-primary">MyApp</h1>
          </Link>
          <h2 className="mt-6 text-2xl font-bold tracking-tight">
            登录到您的账户
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            或者{" "}
            <Link href="/register" className="text-primary hover:underline">
              创建新账户
            </Link>
          </p>
        </div>

        {/* Login Form */}
        <div className="bg-card p-6 rounded-lg shadow-sm border">
          <LoginForm />
        </div>

        {/* OAuth */}
        <div className="space-y-4">
          <Separator />
          <OAuthButtons />
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-muted-foreground">
          登录即表示您同意我们的{" "}
          <Link href="/terms" className="underline hover:text-primary">
            服务条款
          </Link>{" "}
          和{" "}
          <Link href="/privacy" className="underline hover:text-primary">
            隐私政策
          </Link>
        </p>
      </div>
    </div>
  );
}
```

4.2 实现仪表盘布局：

```typescript
// src/app/(dashboard)/layout.tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { useUIStore } from "@/stores/ui-store";
import { cn } from "@/lib/utils/cn";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { isAuthenticated, checkAuth } = useAuthStore();
  const { sidebarOpen } = useUIStore();

  useEffect(() => {
    // 检查认证状态
    if (!isAuthenticated) {
      checkAuth().then((authenticated) => {
        if (!authenticated) {
          router.push("/login");
        }
      });
    }
  }, [isAuthenticated, checkAuth, router]);

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <div
        className={cn(
          "transition-all duration-300",
          sidebarOpen ? "ml-64" : "ml-16"
        )}
      >
        <Header />
        <main className="p-6">{children}</main>
      </div>
    </div>
  );
}
```

4.3 编写组件测试：

```typescript
// src/__tests__/components/button.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { Button } from "@/components/ui/button";
import { describe, it, expect, vi } from "vitest";

describe("Button", () => {
  it("renders with default variant", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole("button", { name: "Click me" })).toBeInTheDocument();
  });

  it("handles click events", async () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click me</Button>);
    
    fireEvent.click(screen.getByRole("button"));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("disables when loading", () => {
    render(<Button loading>Loading</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("shows loading spinner when loading", () => {
    render(<Button loading>Loading</Button>);
    expect(screen.getByTestId("loading-spinner")).toBeInTheDocument();
  });

  it("applies different variants", () => {
    const { rerender } = render(<Button variant="destructive">Delete</Button>);
    expect(screen.getByRole("button")).toHaveClass("bg-destructive");

    rerender(<Button variant="outline">Cancel</Button>);
    expect(screen.getByRole("button")).toHaveClass("border");
  });

  it("applies different sizes", () => {
    const { rerender } = render(<Button size="sm">Small</Button>);
    expect(screen.getByRole("button")).toHaveClass("h-9");

    rerender(<Button size="lg">Large</Button>);
    expect(screen.getByRole("button")).toHaveClass("h-11");
  });
});
```

```typescript
// src/__tests__/hooks/use-data.test.ts
import { renderHook, waitFor } from "@testing-library/react";
import { useData } from "@/hooks/use-data";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

const server = setupServer(
  http.get("/api/test", () => {
    return HttpResponse.json({ message: "Hello" });
  })
);

beforeEach(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("useData", () => {
  it("fetches data on mount", async () => {
    const { result } = renderHook(() =>
      useData<{ message: string }>("/api/test")
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual({ message: "Hello" });
    expect(result.current.error).toBeNull();
  });

  it("handles errors", async () => {
    server.use(
      http.get("/api/test", () => {
        return HttpResponse.json({ message: "Error" }, { status: 500 });
      })
    );

    const { result } = renderHook(() =>
      useData<{ message: string }>("/api/test")
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeDefined();
    expect(result.current.data).toBeNull();
  });
});
```

4.4 编写 E2E 测试：

```typescript
// src/__tests__/e2e/login.spec.ts
import { test, expect } from "@playwright/test";

test.describe("Login Flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
  });

  test("shows login form", async ({ page }) => {
    await expect(page.getByLabel("邮箱")).toBeVisible();
    await expect(page.getByLabel("密码")).toBeVisible();
    await expect(page.getByRole("button", { name: "登录" })).toBeVisible();
  });

  test("validates empty fields", async ({ page }) => {
    await page.getByRole("button", { name: "登录" }).click();
    
    await expect(page.getByText("请输入有效的邮箱地址")).toBeVisible();
    await expect(page.getByText("密码至少8个字符")).toBeVisible();
  });

  test("shows error on invalid credentials", async ({ page }) => {
    await page.getByLabel("邮箱").fill("invalid@example.com");
    await page.getByLabel("密码").fill("wrongpassword");
    await page.getByRole("button", { name: "登录" }).click();
    
    await expect(page.getByText("邮箱或密码错误")).toBeVisible();
  });

  test("redirects to dashboard on success", async ({ page }) => {
    // Mock successful login
    await page.route("/api/auth/login", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          token: "fake-token",
          user: { id: "1", email: "test@example.com", name: "Test User" },
        }),
      });
    });

    await page.getByLabel("邮箱").fill("test@example.com");
    await page.getByLabel("密码").fill("password123");
    await page.getByRole("button", { name: "登录" }).click();

    await expect(page).toHaveURL("/dashboard");
  });
});
```

4.5 无障碍性检查：

```typescript
// src/__tests__/a11y/button-a11y.test.ts
import { render } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";
import { Button } from "@/components/ui/button";

expect.extend(toHaveNoViolations);

describe("Button Accessibility", () => {
  it("has no axe violations", async () => {
    const { container } = render(<Button>Click me</Button>);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("has accessible name", () => {
    const { getByRole } = render(<Button>Submit</Button>);
    expect(getByRole("button", { name: "Submit" })).toBeInTheDocument();
  });

  it("is keyboard accessible", () => {
    const { getByRole } = render(<Button>Press me</Button>);
    const button = getByRole("button", { name: "Press me" });
    
    button.focus();
    expect(button).toHaveFocus();
    
    // Enter key should activate
    button.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
  });

  it("shows focus indicator", () => {
    const { getByRole } = render(<Button>Focus</Button>);
    const button = getByRole("button");
    
    button.focus();
    expect(button).toHaveFocus();
  });
});
```

---

## 技术栈与工具

### 核心框架

| 类别 | 工具 | 版本 | 用途 |
|------|------|------|------|
| 框架 | Next.js | >=14 | React 全栈框架 |
| 路由 | App Router | - | 文件系统路由 |
| 样式 | Tailwind CSS | >=3.4 | 原子化 CSS |
| 组件库 | shadcn/ui | latest | Radix UI 封装 |
| 样式工具 | class-variance-authority | >=0.7 | 变体管理 |
| 样式工具 | clsx/tailwind-merge | latest | 类名合并 |

### 状态管理与数据获取

| 类别 | 工具 | 版本 | 用途 |
|------|------|------|------|
| 状态管理 | Zustand | >=4 | 轻量状态管理 |
| 状态管理 | Jotai | >=2 | 原子化状态 |
| 数据获取 | TanStack Query | >=5 | 服务端状态 |
| 表格 | TanStack Table | >=8 | 高级表格 |
| 表单 | React Hook Form | >=7 | 表单管理 |
| 验证 | Zod | >=3 | Schema 验证 |
| 验证 | @hookform/resolvers | >=3 | 集成 Zod |

### 开发工具

| 类别 | 工具 | 版本 | 用途 |
|------|------|------|------|
| 构建 | Turbopack | - | 快速构建 |
| Lint | ESLint | >=8 | 代码检查 |
| Lint | Prettier | >=3 | 代码格式化 |
| Lint | Ruff | - | 极速 Lint |
| 类型检查 | TypeScript | >=5 | 静态类型 |
| 测试 | Vitest | >=1 | 单元测试 |
| 测试 | Playwright | >=1.27 | E2E 测试 |
| 测试 | Testing Library | >=14 | React 测试 |

### 性能优化

| 类别 | 工具 | 用途 |
|------|------|------|
| 图片优化 | next/image | 自动优化 |
| 字体优化 | next/font | 自托管字体 |
| 组件懒加载 | dynamic import | 代码分割 |
| 预取 | next/link | 预取页面 |

---

## 输出格式

### 标准输出格式

```markdown
# Frontend Developer Output

## 1. 任务总结

**页面**: [页面路径]  
**组件数**: [N]  
**API 集成**: [N] 个端点

## 2. 实现清单

### 页面
- [x] /login - 登录页
- [x] /register - 注册页
- [x] /dashboard - 仪表盘

### 组件
- [x] Button (4 variants)
- [x] Input (with validation)
- [x] Dialog (3 types)
- [x] DataTable (sortable, filterable)

### API
- [x] POST /api/auth/login
- [x] POST /api/auth/register
- [x] GET /api/users/me

## 3. 测试结果

| 测试类型 | 覆盖率 | 状态 |
|----------|--------|------|
| 单元测试 | 85% | ✅ |
| 集成测试 | 70% | ✅ |
| E2E 测试 | 5 scenarios | ✅ |
| Accessibility | WCAG 2.1 AA | ✅ |

## 4. 性能指标

| 指标 | 目标 | 实际 |
|------|------|------|
| LCP | < 2.5s | 1.8s |
| FID | < 100ms | 45ms |
| CLS | < 0.1 | 0.05 |

## 5. 代码质量

- ESLint: 0 errors, 0 warnings
- Prettier: ✅
- TypeScript: ✅ strict mode
```

---

## 验证条件

### 功能验证

1. **页面可访问**: 所有页面在 localhost:3000 可正常访问
2. **表单验证**: 所有表单输入正确验证并显示错误信息
3. **API 集成**: 所有 API 调用正确处理成功和错误情况
4. **路由保护**: 未认证用户被正确重定向到登录页

### 视觉验证

1. **响应式布局**: 在 mobile/tablet/desktop 断点正确显示
2. **主题支持**: Light/Dark 模式正确切换
3. **动画流畅**: 过渡和动画无卡顿

### 技术验证

1. **类型安全**: 无 TypeScript 错误
2. **测试通过**: 所有单元测试和集成测试通过
3. **E2E 通过**: Playwright 测试套件全部通过
4. **无障碍合规**: axe-core 检测无严重问题

### 性能验证

1. **Lighthouse**: Performance >= 90
2. **Core Web Vitals**: 全部达标
3. **Bundle Size**: < 200KB (首屏 JS)

---

## 熔断规则

| 条件 | 动作 | 恢复策略 |
|------|------|----------|
| 构建失败 | 熔断 CI | 修复构建错误 |
| 核心测试失败 | 熔断部署 | 修复失败的测试 |
| Lighthouse < 50 | 熔断性能 | 优化加载性能 |
| Accessibility 失败 | 熔断发布 | 修复无障碍问题 |

---

_Last updated: 2026-04-18_
