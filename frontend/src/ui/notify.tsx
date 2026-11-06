import { useState } from "react";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import { useSubmit } from "../lib/hooks";
import { Banner, Button, Field, Modal, TextArea, TextInput } from "./ui";
import { useToast } from "./toast";

export function NotifyDialog({
  clientId,
  clientName,
  installationId,
  onClose,
  onCreated,
}: {
  clientId: string;
  clientName: string;
  installationId?: string | null;
  onClose: () => void;
  onCreated?: () => void;
}) {
  const toast = useToast();
  const submit = useSubmit();
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!installationId && !message.trim()) {
      submit.setError(new ApiError(0, "Укажите текст, если установка не выбрана", { message: "Укажите текст" }));
      return;
    }
    const ok = await submit.run(async () => {
      const created = await api.createNotification({
        client_id: clientId,
        client_configuration_id: installationId || null,
        title: title.trim() || null,
        message: message.trim() || null,
      });
      toast.success(
        created.length
          ? `Уведомление отправлено: ${created.length}`
          : "Уведомление сохранено",
      );
    });
    if (ok) {
      onCreated?.();
      onClose();
    }
  }

  const formError = submit.error && Object.keys(submit.error.fieldErrors).length === 0 ? submit.error.detail : null;

  return (
    <Modal title={`Сообщить ${clientName}`} onClose={onClose} locked={submit.pending}>
      <form className="stack" onSubmit={onSubmit}>
        {formError ? <Banner>{formError}</Banner> : null}
        <p className="lede">
          {installationId
            ? "Заголовок и текст можно оставить пустыми: Норд соберёт их из установленной и текущей версий."
            : "Без установки нужен текст сообщения. Получатели — активные пользователи клиента."}
        </p>
        <Field label="Заголовок" error={submit.error?.fieldErrors.title}>
          <TextInput value={title} maxLength={255} onChange={(event) => setTitle(event.target.value)} />
        </Field>
        <Field label="Текст" error={submit.error?.fieldErrors.message}>
          <TextArea value={message} onChange={(event) => setMessage(event.target.value)} />
        </Field>
        <div className="modal-actions">
          <Button tone="quiet" onClick={onClose} disabled={submit.pending}>
            Отмена
          </Button>
          <Button type="submit" disabled={submit.pending}>
            {submit.pending ? "Отправляем…" : "Отправить"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
