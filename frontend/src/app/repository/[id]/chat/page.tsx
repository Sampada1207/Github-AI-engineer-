"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import { fetchApi } from "@/lib/api";
import { AppLayout } from "@/components/shared/app-layout";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { 
  MessageSquare, Send, Bot, User, Loader2, FileCode, CheckCircle, 
  HelpCircle, Sparkles 
} from "lucide-react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Array<{
    file_path: string;
    start_line: number;
    end_line: number;
  }>;
  created_at: string;
}

interface Chat {
  id: string;
  title: string;
  created_at: string;
}

export default function RepoChatPage() {
  const params = useParams();
  const repoId = params.id as string;

  const [repo, setRepo] = useState<any>(null);
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeChat, setActiveChat] = useState<Chat | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [chatLoading, setChatLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const loadChats = async () => {
      try {
        const repoData = await fetchApi(`/repositories/${repoId}`);
        setRepo(repoData);

        const chatList = await fetchApi(`/repositories/${repoId}/chats`);
        setChats(chatList);

        if (chatList.length > 0) {
          // Open latest chat
          const latestChat = chatList[chatList.length - 1];
          setActiveChat(latestChat);
          loadMessages(latestChat.id);
        } else {
          // Create new chat
          const newChat = await fetchApi(`/repositories/${repoId}/chats`, {
            method: "POST",
            body: JSON.stringify({
              repository_id: repoId,
              title: "Code Intelligence Discussion"
            }),
          });
          setChats([newChat]);
          setActiveChat(newChat);
          setMessages([]);
        }
      } catch (err) {
        console.error(err);
      } finally {
        setChatLoading(false);
      }
    };
    loadChats();
  }, [repoId]);

  const loadMessages = async (chatId: string) => {
    try {
      const msgList = await fetchApi(`/chats/${chatId}/messages`);
      setMessages(msgList);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !activeChat || sending) return;

    const userMessageText = input.trim();
    setInput("");
    setSending(true);

    // Append optimistic user message locally
    const userOptimisticMsg: Message = {
      id: "opt_" + Date.now(),
      role: "user",
      content: userMessageText,
      created_at: new Date().toISOString()
    };
    setMessages((prev) => [...prev, userOptimisticMsg]);

    try {
      const response = await fetchApi(`/chats/${activeChat.id}/messages`, {
        method: "POST",
        body: JSON.stringify({ content: userMessageText }),
      });
      
      // Update messages list with official user & assistant records
      setMessages((prev) => {
        // filter out optimistic msg
        const filtered = prev.filter(m => !m.id.startsWith("opt_"));
        return [...filtered, response];
      });
    } catch (err: any) {
      console.error(err);
      const errorMsg: Message = {
        id: "err_" + Date.now(),
        role: "assistant",
        content: `Error generating response: ${err.message || "Something went wrong."}`,
        created_at: new Date().toISOString()
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setSending(false);
    }
  };

  const handleCreateNewThread = async () => {
    try {
      setChatLoading(true);
      const newChat = await fetchApi(`/repositories/${repoId}/chats`, {
        method: "POST",
        body: JSON.stringify({
          repository_id: repoId,
          title: `Discussion #${chats.length + 1}`
        }),
      });
      setChats((prev) => [...prev, newChat]);
      setActiveChat(newChat);
      setMessages([]);
    } catch (err) {
      console.error(err);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <AppLayout repositoryId={repoId} repositoryName={repo?.name}>
      <div className="flex h-[calc(100vh-140px)] gap-6">
        
        {/* Thread Selector (Left sidebar inside chat) */}
        <div className="w-64 hidden md:flex flex-col border border-slate-900 bg-slate-900/30 backdrop-blur-md rounded-xl p-4 gap-4 h-full">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">Threads</span>
            <Button variant="ghost" size="sm" onClick={handleCreateNewThread} className="text-purple-400 hover:text-purple-300 p-1 text-xs gap-1">
              New Thread
            </Button>
          </div>
          
          <ScrollArea className="flex-1">
            <div className="space-y-1.5 pr-3">
              {chats.map((c) => (
                <button
                  key={c.id}
                  onClick={() => {
                    setActiveChat(c);
                    loadMessages(c.id);
                  }}
                  className={`w-full text-left px-3 py-2.5 rounded-lg text-xs font-semibold flex items-center gap-2 truncate transition-colors ${
                    activeChat?.id === c.id
                      ? "bg-purple-600/10 text-purple-400 border border-purple-500/15"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/50"
                  }`}
                >
                  <MessageSquare className="h-3.5 w-3.5 flex-shrink-0" />
                  <span className="truncate">{c.title}</span>
                </button>
              ))}
            </div>
          </ScrollArea>
        </div>

        {/* Chat Window (Right section) */}
        <div className="flex-1 flex flex-col border border-slate-900 bg-slate-900/30 backdrop-blur-md rounded-xl h-full overflow-hidden">
          
          {/* Header */}
          <div className="px-5 py-4 border-b border-slate-900 flex justify-between items-center bg-slate-950/40">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-purple-600/10 text-purple-400 border border-purple-500/10">
                <Sparkles className="h-4.5 w-4.5" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-slate-200">Repository Copilot</h2>
                <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">LangGraph Code Intelligence Agent</p>
              </div>
            </div>
            {repo && (
              <span className="text-[10px] bg-slate-800 border border-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">
                {repo.name}
              </span>
            )}
          </div>

          {/* Messages Logs Area */}
          <ScrollArea className="flex-1 p-5">
            <div className="space-y-6">
              {chatLoading ? (
                <div className="flex justify-center items-center py-20">
                  <Loader2 className="h-6 w-6 text-purple-500 animate-spin" />
                </div>
              ) : messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center text-center py-20 space-y-3">
                  <HelpCircle className="h-10 w-10 text-slate-600" />
                  <div>
                    <h4 className="text-sm font-bold text-slate-300">Ask Anything About Your Repo</h4>
                    <p className="text-xs text-slate-500 mt-1 max-w-sm">
                      Explain modules, ask where data flows, locate logic errors, or request mock unit test templates.
                    </p>
                  </div>
                </div>
              ) : (
                messages.map((msg) => {
                  const isAssistant = msg.role === "assistant";
                  return (
                    <div
                      key={msg.id}
                      className={`flex gap-3.5 max-w-4xl ${isAssistant ? "" : "ml-auto flex-row-reverse"}`}
                    >
                      {/* Avatar */}
                      <div className={`h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0 border ${
                        isAssistant 
                          ? "bg-purple-600/10 text-purple-400 border-purple-500/10" 
                          : "bg-indigo-600/10 text-indigo-400 border-indigo-500/10"
                      }`}>
                        {isAssistant ? <Bot className="h-4 w-4" /> : <User className="h-4 w-4" />}
                      </div>

                      {/* Content Bubble */}
                      <div className="space-y-2.5 max-w-[85%]">
                        <div className={`px-4 py-3 rounded-xl text-sm leading-relaxed border ${
                          isAssistant
                            ? "bg-slate-950/60 border-slate-900 text-slate-200"
                            : "bg-purple-600/10 border-purple-500/15 text-slate-100"
                        }`}>
                          <p className="whitespace-pre-wrap">{msg.content}</p>
                        </div>
                        
                        {/* Citations */}
                        {isAssistant && msg.citations && msg.citations.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 pl-1.5">
                            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider flex items-center mr-1">Citations:</span>
                            {msg.citations.map((cit, idx) => (
                              <span 
                                key={idx} 
                                className="inline-flex items-center gap-1 text-[10px] bg-slate-900 border border-slate-800 hover:border-purple-500/30 text-slate-300 hover:text-slate-100 px-2 py-0.5 rounded cursor-pointer transition-colors"
                                title={`Lines ${cit.start_line}-${cit.end_line}`}
                              >
                                <FileCode className="h-3 w-3 text-purple-400" />
                                {cit.file_path.split("/").pop()}:{cit.start_line}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
              {sending && (
                <div className="flex gap-3.5">
                  <div className="h-8 w-8 rounded-lg flex items-center justify-center bg-purple-600/10 text-purple-400 border border-purple-500/10">
                    <Bot className="h-4 w-4" />
                  </div>
                  <div className="px-4 py-3 bg-slate-950/60 border border-slate-900 text-slate-400 rounded-xl text-sm flex items-center gap-2">
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-purple-400" />
                    <span>Analyzing indexed code blocks...</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>

          {/* Form Input Area */}
          <div className="p-4 border-t border-slate-900 bg-slate-950/40">
            <form onSubmit={handleSend} className="flex gap-3">
              <Input
                placeholder="Ask about architecture, trace functions, or write unit tests..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={sending}
                className="bg-slate-950 border-slate-900 focus:border-purple-500 text-slate-100"
              />
              <Button type="submit" disabled={sending || !input.trim()} className="bg-purple-600 hover:bg-purple-500 text-white px-4">
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </div>

      </div>
    </AppLayout>
  );
}
