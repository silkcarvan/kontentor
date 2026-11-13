import worker from "../../web/src/index";

export const onRequest: PagesFunction = async (context) => {
  return worker.fetch(context.request, context.env as any);
};
