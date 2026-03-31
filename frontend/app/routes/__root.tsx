import {
  createRootRouteWithContext,
  HeadContent,
  Outlet,
  ScrollRestoration,
} from "@tanstack/react-router";
import { QueryClient } from "@tanstack/react-query";
import { Body, Html, Head, Meta, Scripts } from "@tanstack/start";

interface RouterContext {
  queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<RouterContext>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "HomeBidder — AI Offer Strategy" },
    ],
    links: [{ rel: "icon", href: "/favicon.ico" }],
  }),
  component: RootComponent,
});

function RootComponent() {
  return (
    <Html>
      <Head>
        <HeadContent />
      </Head>
      <Body>
        <div className="min-h-screen bg-gray-50">
          <nav className="bg-white border-b border-gray-200 px-6 py-4">
            <span className="text-xl font-semibold text-blue-700">HomeBidder</span>
            <span className="ml-2 text-sm text-gray-500">AI Offer Strategy</span>
          </nav>
          <Outlet />
        </div>
        <ScrollRestoration />
        <Scripts />
      </Body>
    </Html>
  );
}
