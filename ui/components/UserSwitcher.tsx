"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useDispatch, useSelector } from "react-redux";
import { AppDispatch, RootState } from "@/store/store";
import { setUserId } from "@/store/profileSlice";
import { User, LogIn } from "lucide-react";

export function UserSwitcher() {
  const dispatch = useDispatch<AppDispatch>();
  const currentUserId = useSelector((state: RootState) => state.profile.userId);
  const [newUserId, setNewUserId] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const handleUserSwitch = () => {
    if (newUserId.trim()) {
      dispatch(setUserId(newUserId.trim()));
      setIsDialogOpen(false);
      setNewUserId("");
      // Reload the page to refresh all data with new user
      window.location.reload();
    }
  };

  return (
    <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            className="flex items-center gap-2 border-zinc-700/50 bg-zinc-900 hover:bg-zinc-800"
          >
            <User className="h-4 w-4" />
            <span className="max-w-[100px] truncate">{currentUserId}</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>当前用户</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem disabled className="text-sm text-zinc-400">
            {currentUserId}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DialogTrigger asChild>
            <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
              <LogIn className="mr-2 h-4 w-4" />
              切换用户
            </DropdownMenuItem>
          </DialogTrigger>
        </DropdownMenuContent>
      </DropdownMenu>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>切换用户</DialogTitle>
          <DialogDescription>
            输入新的用户 ID 来切换用户。每个用户拥有独立的记忆数据。
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <div className="space-y-2">
            <label htmlFor="user-id" className="text-sm font-medium">
              当前用户 ID
            </label>
            <Input
              id="current-user-id"
              value={currentUserId}
              disabled
              className="bg-zinc-900"
            />
          </div>
          <div className="space-y-2 mt-4">
            <label htmlFor="new-user-id" className="text-sm font-medium">
              新用户 ID
            </label>
            <Input
              id="new-user-id"
              placeholder="输入用户 ID"
              value={newUserId}
              onChange={(e) => setNewUserId(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleUserSwitch();
                }
              }}
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => {
              setIsDialogOpen(false);
              setNewUserId("");
            }}
          >
            取消
          </Button>
          <Button onClick={handleUserSwitch} disabled={!newUserId.trim()}>
            切换
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}


