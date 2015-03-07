; -*-Emacs-Lisp-*-

(defgroup fly-hack nil
  "Flymake using tox local pep8"
  :prefix "fly-hack-"
  :group 'tools)

(defcustom fly-hack-helper "fly-hack"
  "*The pathname of the fly-hack helper script to use"
  :type 'string
  :group 'fly-hack)


;;; The following helper makes this mode tramp safe because we build
;;; temp files of all remote tramp buffers. It does mean that in the
;;; tramp case we fall back to more basic logic, don't do all the tox
;;; localized fun, but that's the price you pay for it.
(defun flymake-create-temp-with-folder-structure-safe (file-name prefix)
  (unless (stringp file-name)
    (error "Invalid file-name"))

  (let* ((dir (file-name-directory (replace-regexp-in-string "[:@]" "_" file-name)))
         ;; Not sure what this slash-pos is all about, but I guess it's just
         ;; trying to remove the leading / of absolute file names.
         (slash-pos (string-match "/" dir))
         (temp-dir  (expand-file-name (substring dir (1+ slash-pos))
                                      (flymake-get-temp-dir))))

    (file-truename (expand-file-name (file-name-nondirectory file-name)
                                     temp-dir))))

(when (load "flymake" t)
  ;; disable run in place so that this is safe for tramp usage
  (setq flymake-run-in-place nil)
  (defun flymake-python-init ()
    (let* ((temp-file (flymake-init-create-temp-buffer-copy
                       'flymake-create-temp-with-folder-structure-safe))
           (local-file (file-relative-name
                        temp-file
                        (file-name-directory buffer-file-name))))
      (list fly-hack-helper (list local-file))))

  (add-to-list 'flymake-allowed-file-name-masks
               '("\\.py\\'" flymake-python-init)))

;;; enable flymake-mode for python mode
(add-hook 'python-mode-hook (lambda () (flymake-mode 1)))

(provide 'fly-hack)
